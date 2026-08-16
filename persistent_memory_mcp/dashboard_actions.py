"""Safe maintenance actions for the localhost Dashboard.

All destructive operations reuse the existing signed preview/confirmation contracts.
The HTTP layer never receives arbitrary destination paths and never performs raw SQL
mutations directly.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .isolation import normalize_scope
from .maintenance import BackupService, RestorePlan, RestoreService
from .retention import (
    ALLOWED_MEMORY_TYPES,
    ForgetPlan,
    assert_confirmation_unused,
    build_forget_plan,
    create_confirmation_token,
    mark_confirmation_used,
    validate_confirmation_token,
)
from .security import redact_sensitive_value
from .storage import SQLiteStorage

MAX_DELETE_IDS = 100
_RESTORE_PLANS: dict[str, RestorePlan] = {}


class DashboardActionError(ValueError):
    """Raised when a Dashboard maintenance action cannot be performed safely."""


def _safe_backup_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or name != Path(name).name or name in {".", ".."}:
        raise DashboardActionError(
            "backup_name must be a file name inside the configured backup directory"
        )
    if not name.endswith(".db"):
        raise DashboardActionError("backup_name must end in .db")
    return name


def _forget_plan_from_dict(payload: Mapping[str, Any]) -> ForgetPlan:
    allowed = {item.name for item in fields(ForgetPlan)}
    unknown = set(payload) - allowed
    missing = allowed - set(payload)
    if unknown:
        raise DashboardActionError(
            f"unsupported deletion plan fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise DashboardActionError(
            f"deletion plan is missing fields: {', '.join(sorted(missing))}"
        )
    normalized = dict(payload)
    normalized["record_ids"] = tuple(str(item) for item in payload.get("record_ids", ()))
    try:
        return ForgetPlan(**normalized)
    except TypeError as exc:
        raise DashboardActionError("deletion plan is invalid") from exc


class DashboardMaintenanceActions:
    """Local-only backup/restore/delete adapter using existing safety contracts."""

    def __init__(
        self,
        storage: SQLiteStorage,
        *,
        owner_id: str,
        backup_directory: str | Path | None,
    ) -> None:
        owner = str(owner_id or "").strip()
        if not owner:
            raise DashboardActionError("owner_id is required for maintenance actions")
        self.storage = storage
        self.owner_id = owner
        self.backup_directory = (
            Path(backup_directory).expanduser().resolve()
            if backup_directory is not None
            else None
        )

    def create_backup(self) -> dict[str, Any]:
        directory = self._require_backup_directory()
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        destination = directory / f"dashboard-{stamp}-{uuid4().hex[:8]}.db"
        result = BackupService(self.storage.path).create_backup(destination)
        return {
            "status": "ok",
            "backup_name": result.backup_path.name,
            "manifest_name": result.manifest_path.name,
            "created_at": result.created_at.isoformat(),
            "backup_size_bytes": result.backup_size_bytes,
            "sha256": result.sha256,
            "schema_version": result.schema_version,
            "integrity_status": result.integrity_status,
        }

    def plan_restore(
        self,
        *,
        backup_name: str,
        confirmation_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        directory = self._require_backup_directory()
        name = _safe_backup_name(backup_name)
        backup = (directory / name).resolve()
        if backup.parent != directory:
            raise DashboardActionError("backup_name escapes the configured backup directory")
        if backup.is_symlink():
            raise DashboardActionError("restore backups cannot be symbolic links")
        service = RestoreService(self.storage.path)
        plan, token = service.plan_restore(
            backup,
            confirmation_ttl_seconds=confirmation_ttl_seconds,
        )
        _RESTORE_PLANS[plan.fingerprint] = plan
        return {
            "status": "preview",
            "plan_id": plan.fingerprint,
            "backup_name": backup.name,
            "backup_sha256": plan.backup_sha256,
            "backup_size_bytes": plan.backup_size_bytes,
            "backup_schema_version": plan.backup_schema_version,
            "target_schema_version": plan.target_schema_version,
            "required_free_bytes": plan.required_free_bytes,
            "disk_free_bytes": plan.disk_free_bytes,
            "created_at": plan.created_at,
            "expires_at": plan.expires_at,
            "confirmation_token": token,
        }

    def execute_restore(self, *, plan_id: str, confirmation_token: str) -> dict[str, Any]:
        fingerprint = str(plan_id or "").strip()
        plan = _RESTORE_PLANS.get(fingerprint)
        if plan is None:
            raise DashboardActionError("restore plan is missing or no longer available")
        result = RestoreService(self.storage.path).execute_restore(plan, confirmation_token)
        _RESTORE_PLANS.pop(fingerprint, None)
        safety = Path(str(result.get("safety_backup_path") or ""))
        safety_manifest = Path(str(result.get("safety_manifest_path") or ""))
        return {
            "status": "ok",
            "fingerprint": str(result.get("fingerprint") or ""),
            "restored_sha256": str(result.get("restored_sha256") or ""),
            "schema_version": int(result.get("schema_version") or 0),
            "safety_backup_name": safety.name,
            "safety_manifest_name": safety_manifest.name,
        }

    def plan_deletion(
        self,
        *,
        memory_type: str,
        project_id: str,
        record_ids: list[str],
        confirmation_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        table = str(memory_type or "").strip()
        project = str(project_id or "").strip()
        if table not in ALLOWED_MEMORY_TYPES or table not in self.storage.allowed_tables:
            raise DashboardActionError("unsupported memory type for local Dashboard deletion")
        if not project:
            raise DashboardActionError("project_id is required")
        requested = tuple(
            dict.fromkeys(str(item).strip() for item in record_ids if str(item).strip())
        )
        if not requested:
            raise DashboardActionError("record_ids are required")
        if len(requested) > MAX_DELETE_IDS:
            raise DashboardActionError(
                f"at most {MAX_DELETE_IDS} record_ids may be planned at once"
            )
        self._assert_project(project)
        selected = self._select_deletion_records(table, project, requested)
        scope = normalize_scope(self.owner_id, project_id=project)
        plan = build_forget_plan(
            table,
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
            "missing_record_ids": sorted(set(requested) - set(plan.record_ids)),
        }

    def execute_deletion(
        self,
        *,
        plan: Mapping[str, Any],
        confirmation_token: str,
    ) -> dict[str, Any]:
        parsed = _forget_plan_from_dict(plan)
        if parsed.owner_id != self.owner_id:
            raise DashboardActionError("deletion plan owner does not match the active owner")
        self._assert_project(parsed.project_id)
        assert_confirmation_unused(parsed.fingerprint)
        validate_confirmation_token(parsed, confirmation_token)
        current = self._select_deletion_records(
            parsed.memory_type,
            parsed.project_id,
            parsed.record_ids,
        )
        current_ids = {str(row["id"]) for row in current}
        executable_ids = tuple(item for item in parsed.record_ids if item in current_ids)
        deleted = self.storage.delete_ids(
            parsed.memory_type,
            executable_ids,
            owner_id=parsed.owner_id,
            project_id=parsed.project_id,
        )
        mark_confirmation_used(parsed.fingerprint)
        self.storage.insert(
            "timeline_events",
            {
                "project_id": parsed.project_id,
                "owner_id": parsed.owner_id,
                "event_type": "memory.deleted",
                "summary": "Executed a confirmed local Dashboard memory deletion plan.",
                "payload": {
                    "memory_type": parsed.memory_type,
                    "fingerprint": parsed.fingerprint,
                    "planned_count": parsed.count,
                    "deleted_count": deleted,
                    "record_ids": list(executable_ids),
                },
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

    def _require_backup_directory(self) -> Path:
        if self.backup_directory is None:
            raise DashboardActionError("backup directory is not configured")
        return self.backup_directory

    def _assert_project(self, project_id: str) -> None:
        with self.storage.connect() as connection:
            row = connection.execute(
                "select 1 from projects where id=? and owner_id=?",
                (project_id, self.owner_id),
            ).fetchone()
        if row is None:
            raise DashboardActionError("project does not exist inside the active owner scope")

    def _select_deletion_records(
        self,
        table: str,
        project_id: str,
        record_ids: tuple[str, ...] | list[str],
    ) -> list[dict[str, Any]]:
        ids = tuple(dict.fromkeys(str(item).strip() for item in record_ids if str(item).strip()))
        if not ids:
            return []
        with self.storage.connect() as connection:
            columns = {
                str(row[1])
                for row in connection.execute(f'pragma table_info("{table}")').fetchall()
            }
            required = {"id", "owner_id", "project_id"}
            if not required.issubset(columns):
                raise DashboardActionError(
                    "memory type does not support scoped local Dashboard deletion"
                )
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(
                f'select id, owner_id, project_id from "{table}" '
                f'where owner_id=? and project_id=? and id in ({placeholders})',
                [self.owner_id, project_id, *ids],
            ).fetchall()
        return [dict(row) for row in rows]


def safe_action_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Redact action payloads defensively before emitting them through HTTP."""
    return redact_sensitive_value(dict(payload)).value
