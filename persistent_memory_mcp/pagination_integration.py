"""Paginated high-volume MCP reads backed by local SQLite keyset cursors."""

from __future__ import annotations

import os
from typing import Any, Callable

from .pagination import PaginationError
from .security import redact_sensitive_value
from .storage import SQLiteStorage

_HISTORY_TABLES = {
    "timeline": "timeline_events",
    "sessions": "sessions",
    "checkpoints": "checkpoints",
    "tasks": "tasks",
    "warnings": "warnings",
    "decisions": "decisions",
}


def _replace_tool(server_module: Any, name: str, function: Callable[..., Any]) -> None:
    tools = getattr(getattr(server_module, "server", None), "_tools", None)
    if isinstance(tools, dict):
        tools[name] = function
    handlers = getattr(server_module, "TOOL_HANDLERS", None)
    if isinstance(handlers, dict) and name in handlers:
        handlers[name] = function


def _register_tool(
    server_module: Any,
    name: str,
    function: Callable[..., Any],
    description: str,
) -> None:
    function.__name__ = name
    setattr(server_module, name, function)
    tools = getattr(getattr(server_module, "server", None), "_tools", None)
    if isinstance(tools, dict) and name in tools:
        tools[name] = function
        return
    try:
        server_module.server.tool(name=name, description=description)(function)
    except Exception:
        # FastMCP variants differ in registration internals. Runtime tests verify
        # tool visibility where the registry is available.
        pass


def _local_storage(client: Any) -> SQLiteStorage | None:
    storage = getattr(client, "storage", None)
    return storage if isinstance(storage, SQLiteStorage) else None


def install_paginated_reads(server_module: Any) -> None:
    """Install bounded project-history reads while preserving legacy timeline callers."""
    if getattr(server_module, "_pagination_reads_installed", False):
        return

    original_timeline = server_module.get_project_timeline

    def list_project_history_page(
        kind: str = "timeline",
        project_id: str | None = None,
        owner_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        try:
            table = _HISTORY_TABLES.get(str(kind).strip().casefold())
            if table is None:
                raise ValueError(
                    "kind must be timeline, sessions, checkpoints, tasks, warnings, or decisions"
                )
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=True,
            )
            storage = _local_storage(client)
            if storage is None:
                raise PaginationError(
                    "keyset project-history pagination currently requires the local SQLite backend"
                )
            resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
            page = storage.select_page(
                table,
                {"owner_id": resolved_owner, "project_id": project["id"]},
                limit=limit,
                cursor=cursor,
            )
            payload = {
                "status": "ok",
                "project_id": project["id"],
                "kind": kind,
                "records": page.items,
                "returned_count": len(page.items),
                "has_more": page.has_more,
                "next_cursor": page.next_cursor,
                "cursor_version": page.cursor_version,
                "limit": page.limit,
                "order_by": page.order_by,
                "descending": page.descending,
            }
            return redact_sensitive_value(payload).value
        except Exception as exc:
            return {"error": str(exc), "tool": "list_project_history_page"}

    def get_project_timeline(
        project_id: str | None = None,
        owner_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Return one deterministic timeline page on SQLite, with remote compatibility fallback."""
        client = server_module._client(owner_id)
        storage = _local_storage(client)
        if storage is None:
            if cursor:
                return {
                    "error": "cursor pagination currently requires the local SQLite backend",
                    "tool": "get_project_timeline",
                }
            return original_timeline(
                project_id=project_id,
                owner_id=owner_id,
                limit=limit,
            )
        result = list_project_history_page(
            kind="timeline",
            project_id=project_id,
            owner_id=owner_id,
            limit=limit,
            cursor=cursor,
        )
        if "error" in result:
            return {"error": result["error"], "tool": "get_project_timeline"}
        resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
        resolved_project = str(result["project_id"])
        with storage.connect() as connection:
            total = int(
                connection.execute(
                    "select count(*) from timeline_events where owner_id=? and project_id=?",
                    (resolved_owner, resolved_project),
                ).fetchone()[0]
            )
        return {
            "status": "ok",
            "timeline": result["records"],
            "count": total,
            "returned_count": result["returned_count"],
            "has_more": result["has_more"],
            "next_cursor": result["next_cursor"],
            "cursor_version": result["cursor_version"],
        }

    _replace_tool(server_module, "get_project_timeline", get_project_timeline)
    server_module.get_project_timeline = get_project_timeline
    _register_tool(
        server_module,
        "list_project_history_page",
        list_project_history_page,
        "Lista historial de proyecto con paginacion keyset acotada y cursor opaco.",
    )
    server_module._pagination_reads_installed = True
