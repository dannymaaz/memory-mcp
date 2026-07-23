"""Runtime integration between the legacy MCP server and hybrid search core."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Callable

from .hybrid_search import EmbeddingProvider, hybrid_search


def build_hybrid_search_tool(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Build a server-compatible search tool using the hybrid search engine."""

    def search_semantic_memory(
        query: str,
        project_id: str | None = None,
        owner_id: str | None = None,
        query_embedding: list[float] | None = None,
        limit: int = 5,
        source_types: list[str] | None = None,
        minimum_score: float = 0.05,
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        try:
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=True,
            )
            rows = server_module._table_select(
                client,
                "memory_documents",
                {"project_id": project["id"]},
            )
            if source_types:
                allowed = set(source_types)
                rows = [row for row in rows if row.get("source_type") in allowed]

            provider = EmbeddingProvider(
                provider=os.getenv("MEMORY_EMBEDDING_PROVIDER", "local"),
                max_calls=max(1, len(rows) + 1),
            )
            ranked, metrics = hybrid_search(
                query,
                rows,
                provider=provider,
                query_embedding=query_embedding,
                limit=limit,
                minimum_score=minimum_score,
            )
            matches = [
                {
                    **result.item,
                    "lexical_score": result.lexical_score,
                    "semantic_score": result.semantic_score,
                    "hybrid_score": result.hybrid_score,
                }
                for result in ranked
            ]
            return {
                "status": "ok",
                "query": query,
                "matches": matches,
                "match_count": len(matches),
                "search_mode": "hybrid",
                "metrics": asdict(metrics),
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "search_semantic_memory"}

    search_semantic_memory.__name__ = "search_semantic_memory"
    search_semantic_memory.__doc__ = "Busca memoria con ranking lexical y semantico combinado."
    return search_semantic_memory


def _replace_registered_tool(server: Any, name: str, function: Callable[..., Any]) -> bool:
    """Replace a FastMCP tool across supported fallback and upstream layouts."""
    replaced = False
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict) and name in tools:
        tools[name] = function
        replaced = True

    manager = getattr(server, "_tool_manager", None)
    managed_tools = getattr(manager, "_tools", None)
    if isinstance(managed_tools, dict) and name in managed_tools:
        tool = managed_tools[name]
        if hasattr(tool, "fn"):
            tool.fn = function
            replaced = True
        elif hasattr(tool, "function"):
            tool.function = function
            replaced = True
        else:
            managed_tools[name] = function
            replaced = True
    return replaced


def install_hybrid_search(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Install hybrid search without rewriting the large legacy server module."""
    tool = build_hybrid_search_tool(server_module)
    server_module.search_semantic_memory = tool
    if not _replace_registered_tool(server_module.server, "search_semantic_memory", tool):
        try:
            server_module.server.tool(
                name="search_semantic_memory",
                description="Busca memoria con ranking lexical y semantico combinado.",
            )(tool)
        except Exception:
            # Direct module calls still use the integrated function. Upstream FastMCP
            # layouts known by this package are handled above.
            pass
    return tool
