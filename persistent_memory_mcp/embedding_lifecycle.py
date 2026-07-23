"""Persisted embedding lifecycle and bounded project reindexing."""

from __future__ import annotations

import os
from typing import Any, Callable

from .hybrid_search import EmbeddingProvider, content_fingerprint, render_memory_text


def _replace_registered_tool(server: Any, name: str, function: Callable[..., Any]) -> None:
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        tools[name] = function
    manager = getattr(server, "_tool_manager", None)
    managed = getattr(manager, "_tools", None)
    if isinstance(managed, dict) and name in managed:
        tool = managed[name]
        if hasattr(tool, "fn"):
            tool.fn = function
        elif hasattr(tool, "function"):
            tool.function = function
        else:
            managed[name] = function


def embedding_is_current(row: dict[str, Any], provider_name: str) -> bool:
    """Return whether a stored vector still matches the current record content."""
    metadata = row.get("metadata") or {}
    text = render_memory_text(row)
    return (
        bool(row.get("embedding"))
        and metadata.get("embedding_fingerprint") == content_fingerprint(text)
        and metadata.get("embedding_provider") == provider_name
    )


def build_reindex_tool(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Build the MCP-facing embedding reindex tool."""

    def reindex_memory_embeddings(
        project_id: str | None = None,
        owner_id: str | None = None,
        *,
        force: bool = False,
        limit: int = 500,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 5000:
            return {
                "error": "limit must be between 1 and 5000",
                "tool": "reindex_memory_embeddings",
            }
        client = server_module._client(owner_id)
        try:
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=False,
            )
            rows = server_module._table_select(
                client,
                "memory_documents",
                {"project_id": project["id"]},
            )[:limit]
            provider = EmbeddingProvider(
                provider=os.getenv("MEMORY_EMBEDDING_PROVIDER", "local"),
                max_calls=max(1, len(rows)),
                max_retries=int(os.getenv("MEMORY_EMBEDDING_MAX_RETRIES", "2")),
                retry_base_seconds=float(
                    os.getenv("MEMORY_EMBEDDING_RETRY_BASE_SECONDS", "0.25")
                ),
            )
            updated = 0
            skipped = 0
            failed: list[dict[str, str]] = []
            for row in rows:
                if not force and embedding_is_current(row, provider.name):
                    skipped += 1
                    continue
                text = render_memory_text(row)
                try:
                    vector = provider.embed(text)
                    metadata = {
                        **(row.get("metadata") or {}),
                        "embedding_fingerprint": content_fingerprint(text),
                        "embedding_provider": provider.name,
                        "embedding_dimensions": len(vector),
                        "embedding_version": 1,
                    }
                    server_module._table_upsert(
                        client,
                        "memory_documents",
                        {**row, "embedding": vector, "metadata": metadata},
                    )
                    updated += 1
                except Exception as exc:
                    failed.append(
                        {
                            "id": str(row.get("id") or row.get("source_id") or ""),
                            "error": str(exc),
                        }
                    )
            return {
                "status": "ok",
                "project_id": project["id"],
                "scanned": len(rows),
                "updated": updated,
                "skipped": skipped,
                "failed": failed,
                "metrics": {
                    "provider": provider.name,
                    "embedding_calls": provider.calls,
                    "fallback_used": provider.fallback_used,
                    "retries": provider.retries,
                },
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "reindex_memory_embeddings"}

    reindex_memory_embeddings.__name__ = "reindex_memory_embeddings"
    reindex_memory_embeddings.__doc__ = (
        "Reindexa embeddings persistidos de memoria de forma acotada."
    )
    return reindex_memory_embeddings


def install_embedding_lifecycle(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Install the reindex tool once without rewriting the legacy server module."""
    if getattr(server_module, "_embedding_lifecycle_installed", False):
        return server_module.reindex_memory_embeddings
    tool = build_reindex_tool(server_module)
    server_module.reindex_memory_embeddings = tool
    _replace_registered_tool(server_module.server, "reindex_memory_embeddings", tool)
    try:
        server_module.server.tool(
            name="reindex_memory_embeddings",
            description="Reindexa embeddings persistidos de memoria de forma acotada.",
        )(tool)
    except Exception:
        pass
    server_module._embedding_lifecycle_installed = True
    return tool
