"""Retention and selective-forget planning for persistent memory."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass
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
DEFAULT_CONFIRMATION_TTL_SECONDS = 300


@dataclass(frozen=True)
class ForgetPlan:
    """A reviewable plan for a destructive memory operation."""

    memory_type: str
    record_ids: tuple[str, ...]
    owner_id: str
    project_id: str
    dry_run: bool = True
    created_at: str = ""
    expires_at: str = ""
    fingerprint: str = ""

    @property
    def count(self) -> int:
        return len(self.record_ids)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfirmationError(ValueError):
    """Raised when a destructive-operation confirmation is invalid."""


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


def _confirmation_secret(secret: str | None = None) -> bytes:
    resolved = secret or os.getenv("MEMORY_CONFIRMATION_SECRET") or os.getenv("OWNER_ID")
    if not resolved:
        raise ValueError("MEMORY_CONFIRMATION_SECRET or OWNER_ID is required")
    return resolved.encode("utf-8")


def _canonical_payload(
    memory_type: str,
    record_ids: Iterable[str],
    owner_id: str,
    project_id: str,
    created_at: str,
    expires_at: str,
) -> str:
    payload = {
        "memory_type": memory_type,
        "record_ids": sorted(set(record_ids)),
        "owner_id": owner_id,
        "project_id": project_id,
        "created_at": created_at,
        "expires_at": expires_at,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _plan_fingerprint(canonical_payload: str) -> str:
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def create_confirmation_token(plan: ForgetPlan, *, secret: str | None = None) -> str:
    """Create a signed confirmation token bound to an exact deletion plan."""
    if not plan.fingerprint or not plan.created_at or not plan.expires_at:
        raise ValueError("plan must include fingerprint and expiry metadata")
    signature = hmac.new(
        _confirmation_secret(secret),
        plan.fingerprint.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{plan.fingerprint}.{signature}"


def validate_confirmation_token(
    plan: ForgetPlan,
    token: str,
    *,
    secret: str | None = None,
    now: datetime | None = None,
) -> None:
    """Validate that a token matches an unchanged, non-expired plan."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    expires_at = _parse_timestamp(plan.expires_at)
    if expires_at is None or expires_at <= current.astimezone(UTC):
        raise ConfirmationError("confirmation plan has expired")

    try:
        token_fingerprint, token_signature = token.split(".", 1)
    except ValueError as exc:
        raise ConfirmationError("invalid confirmation token format") from exc

    canonical = _canonical_payload(
        plan.memory_type,
        plan.record_ids,
        plan.owner_id,
        plan.project_id,
        plan.created_at,
        plan.expires_at,
    )
    expected_fingerprint = _plan_fingerprint(canonical)
    if not hmac.compare_digest(plan.fingerprint, expected_fingerprint):
        raise ConfirmationError("deletion plan has changed")
    if not hmac.compare_digest(token_fingerprint, expected_fingerprint):
        raise ConfirmationError("confirmation token does not match this plan")

    expected_signature = hmac.new(
        _confirmation_secret(secret),
        expected_fingerprint.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(token_signature, expected_signature):
        raise ConfirmationError("invalid confirmation token signature")


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
    confirmation_ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS,
    now: datetime | None = None,
) -> ForgetPlan:
    """Build a scope-validated deletion plan without deleting anything."""
    if memory_type not in ALLOWED_MEMORY_TYPES:
        raise ValueError(f"unsupported memory type: {memory_type}")
    if scope.project_id is None:
        raise ValueError("project_id is required for deletion")
    if confirmation_ttl_seconds < 1 or confirmation_ttl_seconds > 3600:
        raise ValueError("confirmation_ttl_seconds must be between 1 and 3600")

    ids: list[str] = []
    for record in records:
        try:
            assert_record_access(record, scope)
        except IsolationError:
            raise
        record_id = str(record.get("id", "")).strip()
        if record_id:
            ids.append(record_id)

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    created_at = current.isoformat()
    expires_at = (current + timedelta(seconds=confirmation_ttl_seconds)).isoformat()
    record_ids = tuple(dict.fromkeys(ids))
    canonical = _canonical_payload(
        memory_type,
        record_ids,
        scope.owner_id,
        scope.project_id,
        created_at,
        expires_at,
    )
    return ForgetPlan(
        memory_type=memory_type,
        record_ids=record_ids,
        owner_id=scope.owner_id,
        project_id=scope.project_id,
        dry_run=dry_run,
        created_at=created_at,
        expires_at=expires_at,
        fingerprint=_plan_fingerprint(canonical),
    )
