"""MCP integration for previewed and explicitly confirmed local SQLite restore."""

from __future__ import annotations

from typing import Any, Callable

from .maintenance import RestorePlan, RestoreService
from .settings import RuntimeSettings
from .tool_registry import ToolRegistry, get_tool_registry


def install_verified_restore(
    server_module: Any,
    settings: RuntimeSettings | None = None,
    *,
    registry: ToolRegistry | None = None,
) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Install local restore preview and execution tools once."""
    if getattr(server_module, "_verified_restore_installed", False):
        return server_module.plan_memory_restore, server_module.execute_memory_restore

    def _service() -> RestoreService:
        active_settings = settings or RuntimeSettings.from_env()
        if active_settings.backend != "sqlite":
            raise RuntimeError("verified restore currently supports the local SQLite backend only")
        return RestoreService(active_settings.sqlite_path)

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
    active_registry = registry or get_tool_registry(server_module)
    active_registry.register(
        "plan_memory_restore",
        "Previsualiza un restore SQLite verificado y genera una confirmacion ligada al plan.",
        plan_memory_restore,
    )
    active_registry.register(
        "execute_memory_restore",
        "Ejecuta un restore SQLite verificado solo con el plan confirmado y sin cambios.",
        execute_memory_restore,
    )
    server_module._verified_restore_installed = True
    return plan_memory_restore, execute_memory_restore
