"""MCP integration for previewed and explicitly confirmed memory deletion."""

from __future__ import annotations

import os
from dataclasses import fields
from typing import Any, Callable, Iterable

from .isolation import normalize_scope
from .retention import (
    ALLOWED_MEMORY_TYPES,
    ForgetPlan,
    USED_CONFIRMATION_FINGERPRINTS,
    assert_confirmation_unused,
    build_forget_plan,
    create_confirmation_token,
    mark_confirmation_used,
    select_retention_candidates,
    validate_confirmation_token,
)
from .tool_registry import ToolRegistry, get_tool_registry

# Backward-compatible alias retained for existing tests/importers while the
# consumed-fingerprint set is now shared with Dashboard maintenance actions.
_USED_PLAN_FINGERPRINTS = USED_CONFIRMATION_FINGERPRINTS


def _plan_from_dict(payload: dict[str, Any]) -> ForgetPlan:
    allowed = {item.name for item in fields(ForgetPlan)}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"unsupported plan fields: {', '.join(sorted(unknown))}")
    normalized = dict(payload)
    normalized["record_ids"] = tuple(str(item) for item in payload.get("record_ids", ()))
    return ForgetPlan(**normalized)


def _delete_ids(
    server_module: Any,
    client: Any,
    table: str,
    record_ids: Iterable[str],
    *,
    owner_id: str,
    project_id: str,
) -> int:
    ids = tuple(dict.fromkeys(str(item).strip() for item in record_ids if str(item).strip()))
    if not ids:
        return 0

    storage = getattr(client, "storage", None)
    if storage is not None and hasattr(storage, "delete_ids"):
        return int(
            storage.delete_ids(
                table,
                ids,
                owner_id=owner_id,
                project_id=project_id,
            )
        )

    if server_module._use_database_url():
        sql = server_module.sql
        if sql is None:
            raise RuntimeError("direct database deletion is unavailable")
        with server_module._db_connect() as connection:
            with connection.cursor() as cursor:
                query = sql.SQL(
                    "delete from {} where owner_id = %s and project_id = %s and id = any(%s)"
                ).format(sql.Identifier(table))
                cursor.execute(query, [owner_id, project_id, list(ids)])
                deleted = int(cursor.rowcount)
                connection.commit()
                return deleted

    deleted = 0
    for record_id in ids:
        query = client.table(table).delete()
        query = query.eq("owner_id", owner_id).eq("project_id", project_id).eq("id", record_id)
        result = getattr(query.execute(), "data", None)
        if isinstance(result, dict) and isinstance(result.get("count"), int):
            deleted += int(result["count"])
        elif isinstance(result, list):
            deleted += len(result)
        else:
            deleted += 1
    return deleted


def install_confirmed_deletion(
    server_module: Any,
    *,
    registry: ToolRegistry | None = None,
) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Install preview and execution tools once."""
    if getattr(server_module, "_confirmed_deletion_installed", False):
        return server_module.plan_memory_deletion, server_module.execute_memory_deletion

    def plan_memory_deletion(
        memory_type: str,
        project_id: str,
        owner_id: str | None = None,
        record_ids: list[str] | None = None,
        retention: bool = False,
        archive_after_days: int = 30,
        keep_recent: int = 5,
        confirmation_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
        try:
            if memory_type not in ALLOWED_MEMORY_TYPES:
                raise ValueError(f"unsupported memory type: {memory_type}")
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=resolved_owner,
                create_if_missing=False,
            )
            scope = normalize_scope(resolved_owner, project_id=project["id"])
            rows = server_module._table_select(
                client,
                memory_type,
                {"project_id": project["id"]},
            )
            if retention:
                selected = select_retention_candidates(
                    rows,
                    scope,
                    archive_after_days=archive_after_days,
                    keep_recent=keep_recent,
                )
            else:
                requested = set(str(item) for item in (record_ids or []))
                if not requested:
                    raise ValueError("record_ids are required unless retention is true")
                selected = [row for row in rows if str(row.get("id")) in requested]
            plan = build_forget_plan(
                memory_type,
                selected,
                scope,
                confirmation_ttl_seconds=confirmation_ttl_seconds,
            )
            token = create_confirmation_token(plan)
            return {
                "status": "preview",
                "plan": plan.to_dict(),
                "confirmation_token": token,
                "candidate_count": plan.count,
                "missing_record_ids": sorted(set(record_ids or []) - set(plan.record_ids)),
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "plan_memory_deletion"}

    def execute_memory_deletion(
        plan: dict[str, Any],
        confirmation_token: str,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        try:
            parsed = _plan_from_dict(plan)
            resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
            if parsed.owner_id != resolved_owner:
                raise PermissionError("plan owner does not match the active owner")
            assert_confirmation_unused(parsed.fingerprint)
            validate_confirmation_token(parsed, confirmation_token)

            current = server_module._table_select(
                client,
                parsed.memory_type,
                {"project_id": parsed.project_id},
            )
            current_ids = {
                str(row.get("id"))
                for row in current
                if str(row.get("owner_id")) == parsed.owner_id
            }
            executable_ids = tuple(item for item in parsed.record_ids if item in current_ids)
            deleted = _delete_ids(
                server_module,
                client,
                parsed.memory_type,
                executable_ids,
                owner_id=parsed.owner_id,
                project_id=parsed.project_id,
            )
            mark_confirmation_used(parsed.fingerprint)
            server_module._record_timeline(
                client,
                parsed.project_id,
                parsed.owner_id,
                "memory.deleted",
                "Executed a confirmed local memory deletion plan.",
                {
                    "memory_type": parsed.memory_type,
                    "fingerprint": parsed.fingerprint,
                    "planned_count": parsed.count,
                    "deleted_count": deleted,
                    "record_ids": list(executable_ids),
                },
            )
            return {
                "status": "ok",
                "memory_type": parsed.memory_type,
                "fingerprint": parsed.fingerprint,
                "planned_count": parsed.count,
                "deleted_count": deleted,
                "stale_count": parsed.count - len(executable_ids),
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "execute_memory_deletion"}

    plan_memory_deletion.__name__ = "plan_memory_deletion"
    execute_memory_deletion.__name__ = "execute_memory_deletion"
    active_registry = registry or get_tool_registry(server_module)
    active_registry.register(
        "plan_memory_deletion",
        "Previsualiza un borrado local y genera una confirmacion ligada al plan.",
        plan_memory_deletion,
    )
    active_registry.register(
        "execute_memory_deletion",
        "Ejecuta un plan de borrado local confirmado y sin cambios.",
        execute_memory_deletion,
    )
    server_module._confirmed_deletion_installed = True
    return plan_memory_deletion, execute_memory_deletion
