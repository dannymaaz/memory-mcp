"""MCP integration for previewed and explicitly confirmed local SQLite restore."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from .maintenance import RestorePlan, RestoreService
from .storage import normalize_backend


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


def _register(server_module: Any, name: str, description: str, function: Callable[..., Any]) -> None:
    setattr(server_module, name, function)
    _replace_registered_tool(server_module.server, name, function)
    try:
        server_module.server.tool(name=name, description=description)(function)
    except Exception:
        pass
    handlers = getattr(server_module, "TOOL_HANDLERS", None)
    if isinstance(handlers, dict):
        handlers[name] = function
    schemas = getattr(server_module, "TOOL_SCHEMAS", None)
    if isinstance(schemas, list) and not any(item.get("name") == name for item in schemas):
        schemas.append({"name": name, "description": description})


def install_verified_restore(server_module: Any) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Install local restore preview and execution tools once."""
    if getattr(server_module, "_verified_restore_installed", False):
        return server_module.plan_memory_restore, server_module.execute_memory_restore

    def _service() -> RestoreService:
        backend = normalize_backend(os.getenv("MEMORY_BACKEND") or "sqlite")
        if backend != "sqlite":
            raise RuntimeError("verified restore currently supports the local SQLite backend only")
        target = os.getenv("SQLITE_PATH") or str(Path.home() / ".memory-mcp" / "memory.db")
        return RestoreService(target)

    def plan_memory_restore(
        backup_path: str,
        confirmation_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        try:
            plan, token = _service().plan_restore(
                backup_path,
                confirmation_ttl_seconds=confirmation_ttl_seconds,
            )
            return {
                "status": "preview",
                "plan": plan.to_dict(),
                "confirmation_token": token,
                "safety_backup_required": True,
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "plan_memory_restore"}

    def execute_memory_restore(
        plan: dict[str, Any],
        confirmation_token: str,
    ) -> dict[str, Any]:
        try:
            parsed = RestorePlan.from_dict(plan)
            return _service().execute_restore(parsed, confirmation_token)
        except Exception as exc:
            return {"error": str(exc), "tool": "execute_memory_restore"}

    plan_memory_restore.__name__ = "plan_memory_restore"
    execute_memory_restore.__name__ = "execute_memory_restore"
    _register(
        server_module,
        "plan_memory_restore",
        "Previsualiza un restore SQLite verificado y genera una confirmacion ligada al plan.",
        plan_memory_restore,
    )
    _register(
        server_module,
        "execute_memory_restore",
        "Ejecuta un restore SQLite verificado solo con el plan confirmado y sin cambios.",
        execute_memory_restore,
    )
    server_module._verified_restore_installed = True
    return plan_memory_restore, execute_memory_restore
