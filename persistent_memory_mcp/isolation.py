"""Service-layer ownership and project-boundary validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class IsolationError(PermissionError):
    """Raised when a record crosses an owner or project boundary."""


@dataclass(frozen=True)
class AccessScope:
    """Normalized access boundary for one memory operation."""

    owner_id: str
    project_id: str | None = None
    workspace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("owner_id is required")


def normalize_scope(
    owner_id: str,
    *,
    project_id: str | None = None,
    workspace_id: str | None = None,
) -> AccessScope:
    """Create a bounded scope with normalized identifiers."""
    return AccessScope(
        owner_id=str(owner_id).strip(),
        project_id=str(project_id).strip() if project_id else None,
        workspace_id=str(workspace_id).strip() if workspace_id else None,
    )


def assert_record_access(record: Mapping[str, Any], scope: AccessScope) -> None:
    """Reject records that do not belong to the requested access scope."""
    record_owner = str(record.get("owner_id", "")).strip()
    if not record_owner or record_owner != scope.owner_id:
        raise IsolationError("record does not belong to the active owner")

    if scope.project_id is not None:
        record_project = str(record.get("project_id", record.get("id", ""))).strip()
        if record_project != scope.project_id:
            raise IsolationError("record does not belong to the active project")

    if scope.workspace_id is not None and record.get("workspace_id") is not None:
        record_workspace = str(record.get("workspace_id", "")).strip()
        if record_workspace != scope.workspace_id:
            raise IsolationError("record does not belong to the active workspace")


def owner_project_filters(scope: AccessScope) -> dict[str, str]:
    """Return mandatory filters for database reads and destructive writes."""
    filters = {"owner_id": scope.owner_id}
    if scope.project_id is not None:
        filters["project_id"] = scope.project_id
    return filters


def secure_payload(payload: Mapping[str, Any], scope: AccessScope) -> dict[str, Any]:
    """Attach scope identifiers and reject conflicting caller-supplied values."""
    result = dict(payload)
    supplied_owner = result.get("owner_id")
    if supplied_owner is not None and str(supplied_owner).strip() != scope.owner_id:
        raise IsolationError("payload owner_id conflicts with the active owner")
    result["owner_id"] = scope.owner_id

    if scope.project_id is not None:
        supplied_project = result.get("project_id")
        if supplied_project is not None and str(supplied_project).strip() != scope.project_id:
            raise IsolationError("payload project_id conflicts with the active project")
        result["project_id"] = scope.project_id
    return result
