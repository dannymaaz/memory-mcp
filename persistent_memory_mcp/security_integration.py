"""Runtime-wide sanitization and owner/project isolation guards."""

from __future__ import annotations

import os
from typing import Any, Callable

from .security import sanitize_memory, security_metadata

_TEXT_FIELDS = {
    "content",
    "summary",
    "description",
    "details",
    "message",
    "title",
    "current_goal",
    "completed_work",
    "remaining_work",
    "next_step",
    "project_summary",
    "decision",
    "rationale",
    "warning",
    "prompt",
    "response",
}

_OWNER_SCOPED_TABLES = {
    "workspaces",
    "projects",
    "sessions",
    "session_state",
    "decisions",
    "tasks",
    "warnings",
    "file_memory",
    "file_relations",
    "checkpoints",
    "prompt_patterns",
    "memory_documents",
    "timeline_events",
    "interface_logs",
    "preferences",
    "retention_policies",
}

_PROJECT_SCOPED_TABLES = _OWNER_SCOPED_TABLES - {"workspaces", "projects"}


def _owner_id() -> str:
    return os.getenv("OWNER_ID", "default-owner")


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy while preserving the server's payload shape."""
    clean = dict(payload)
    findings: list[dict[str, Any]] = []
    provenance_value = clean.get("provenance")
    provenance = provenance_value if isinstance(provenance_value, dict) else None

    for key, value in list(clean.items()):
        if key not in _TEXT_FIELDS or not isinstance(value, str):
            continue
        result = sanitize_memory(value, provenance=provenance)
        clean[key] = result.content
        if result.redactions or result.instruction_like or result.truncated:
            findings.append(security_metadata(result)["security"])

    if findings:
        metadata = clean.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        clean["metadata"] = {
            **metadata,
            "security": {
                "sanitized": True,
                "findings": findings,
                "content_trusted": False,
            },
        }
    return clean


def _validate_scope(
    table: str,
    payload: dict[str, Any],
    *,
    raw_select: Callable[..., list[dict[str, Any]]],
    client: Any,
) -> dict[str, Any]:
    """Require owner/project scope and reject cross-owner project access."""
    scoped = dict(payload)
    expected_owner = _owner_id()

    if table in _OWNER_SCOPED_TABLES:
        supplied_owner = scoped.get("owner_id")
        if supplied_owner not in (None, expected_owner):
            raise PermissionError("Cross-owner memory access is not allowed")
        scoped["owner_id"] = expected_owner

    if table in _PROJECT_SCOPED_TABLES:
        project_id = scoped.get("project_id")
        if not project_id:
            raise ValueError(f"project_id is required for table '{table}'")
        project_rows = raw_select(
            client,
            "projects",
            {"id": project_id, "owner_id": expected_owner},
        )
        if not project_rows:
            raise PermissionError("Project does not belong to the active owner")

    if table == "projects" and scoped.get("id"):
        rows = raw_select(client, "projects", {"id": scoped["id"]})
        if rows and rows[0].get("owner_id") not in (None, expected_owner):
            raise PermissionError("Project does not belong to the active owner")

    if table == "workspaces" and scoped.get("id"):
        rows = raw_select(client, "workspaces", {"id": scoped["id"]})
        if rows and rows[0].get("owner_id") not in (None, expected_owner):
            raise PermissionError("Workspace does not belong to the active owner")

    return scoped


def install_security_boundaries(server_module: Any) -> None:
    """Install central sanitization and isolation around all table access."""
    if getattr(server_module, "_security_boundaries_installed", False):
        return

    original_select = server_module._table_select
    original_insert = server_module._table_insert
    original_upsert = server_module._table_upsert

    def secure_select(
        client: Any,
        table: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scoped_filters = dict(filters or {})
        if table in _OWNER_SCOPED_TABLES:
            supplied_owner = scoped_filters.get("owner_id")
            if supplied_owner not in (None, _owner_id()):
                raise PermissionError("Cross-owner memory access is not allowed")
            scoped_filters["owner_id"] = _owner_id()
        rows = original_select(client, table, scoped_filters)
        if table in _PROJECT_SCOPED_TABLES and scoped_filters.get("project_id"):
            projects = original_select(
                client,
                "projects",
                {
                    "id": scoped_filters["project_id"],
                    "owner_id": _owner_id(),
                },
            )
            if not projects:
                raise PermissionError("Project does not belong to the active owner")
        return rows

    def secure_insert(
        client: Any,
        table: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        scoped = _validate_scope(
            table,
            payload,
            raw_select=original_select,
            client=client,
        )
        return original_insert(client, table, _sanitize_payload(scoped))

    def secure_upsert(
        client: Any,
        table: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        scoped = _validate_scope(
            table,
            payload,
            raw_select=original_select,
            client=client,
        )
        return original_upsert(client, table, _sanitize_payload(scoped))

    server_module._table_select = secure_select
    server_module._table_insert = secure_insert
    server_module._table_upsert = secure_upsert
    server_module._security_boundaries_installed = True
