"""Retention and selective-forget planning for persistent memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Mapping

from .isolation import AccessScope, IsolationError, assert_record_access

ALLOWED_MEMORY_TYPES = frozenset(
    {
        "decisions",
        "tasks",
        "warnings",
        "sessions",
        "session_state",
        "checkpoints",
        "file_memory",
        "file_relations",
        "prompt_patterns",
        "memory_documents",
        "timeline_events",
        "interface_logs",
    }
)


@dataclass(frozen=True)
class ForgetPlan:
    """A reviewable plan for a destructive memory operation."""

    memory_type: str
    record_ids: tuple[str, ...]
    owner_id: str
    project_id: str
    dry_run: bool = True

    @property
    def count(self) -> int:
        return len(self.record_ids)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_expired(record: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    """Return whether a record's security expiry has passed."""
    metadata = record.get("metadata") or {}
    security = metadata.get("security") if isinstance(metadata, Mapping) else {}
    expires_at = record.get("expires_at")
    if not expires_at and isinstance(security, Mapping):
        expires_at = security.get("expires_at")
    parsed = _parse_timestamp(expires_at)
    if parsed is None:
        return False
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return parsed <= current.astimezone(UTC)


def select_retention_candidates(
    records: Iterable[Mapping[str, Any]],
    scope: AccessScope,
    *,
    archive_after_days: int = 30,
    keep_recent: int = 5,
    now: datetime | None = None,
) -> list[Mapping[str, Any]]:
    """Select expired or old records while preserving the newest entries."""
    if scope.project_id is None:
        raise ValueError("project_id is required for retention")
    if archive_after_days < 1:
        raise ValueError("archive_after_days must be positive")
    if keep_recent < 0:
        raise ValueError("keep_recent cannot be negative")

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    cutoff = current.astimezone(UTC) - timedelta(days=archive_after_days)

    validated: list[Mapping[str, Any]] = []
    for record in records:
        assert_record_access(record, scope)
        validated.append(record)

    ordered = sorted(
        validated,
        key=lambda row: _parse_timestamp(row.get("created_at")) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    protected_ids = {str(row.get("id")) for row in ordered[:keep_recent]}
    candidates: list[Mapping[str, Any]] = []
    for row in ordered:
        row_id = str(row.get("id", ""))
        if not row_id or row_id in protected_ids:
            continue
        created_at = _parse_timestamp(row.get("created_at"))
        if is_expired(row, now=current) or (created_at is not None and created_at <= cutoff):
            candidates.append(row)
    return candidates


def build_forget_plan(
    memory_type: str,
    records: Iterable[Mapping[str, Any]],
    scope: AccessScope,
    *,
    dry_run: bool = True,
) -> ForgetPlan:
    """Build a scope-validated deletion plan without deleting anything."""
    if memory_type not in ALLOWED_MEMORY_TYPES:
        raise ValueError(f"unsupported memory type: {memory_type}")
    if scope.project_id is None:
        raise ValueError("project_id is required for deletion")

    ids: list[str] = []
    for record in records:
        try:
            assert_record_access(record, scope)
        except IsolationError:
            raise
        record_id = str(record.get("id", "")).strip()
        if record_id:
            ids.append(record_id)

    return ForgetPlan(
        memory_type=memory_type,
        record_ids=tuple(dict.fromkeys(ids)),
        owner_id=scope.owner_id,
        project_id=scope.project_id,
        dry_run=dry_run,
    )
