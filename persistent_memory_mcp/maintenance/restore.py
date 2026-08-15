"""Previewed, confirmed and rollback-aware SQLite restore operations."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sqlite3
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .backup_service import BackupService
from .errors import RestoreConfirmationError, RestoreExecutionError, RestorePlanError
from .manifest import manifest_path_for, sha256_file, verify_backup_manifest

DEFAULT_RESTORE_TTL_SECONDS = 300
MAX_RESTORE_TTL_SECONDS = 3600
_USED_RESTORE_FINGERPRINTS: set[str] = set()


@dataclass(frozen=True)
class RestorePlan:
    """Exact, reviewable plan for replacing one active SQLite database."""

    backup_path: str
    manifest_path: str
    target_path: str
    safety_backup_path: str
    backup_sha256: str
    backup_size_bytes: int
    backup_schema_version: int
    target_size_bytes: int
    target_schema_version: int
    target_mtime_ns: int
    required_free_bytes: int
    disk_free_bytes: int
    created_at: str
    expires_at: str
    fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RestorePlan":
        allowed = {item.name for item in fields(cls)}
        unknown = set(payload) - allowed
        missing = allowed - set(payload)
        if unknown:
            raise RestorePlanError(f"unsupported restore plan fields: {', '.join(sorted(unknown))}")
        if missing:
            raise RestorePlanError(f"restore plan is missing fields: {', '.join(sorted(missing))}")
        try:
            return cls(
                backup_path=str(payload["backup_path"]),
                manifest_path=str(payload["manifest_path"]),
                target_path=str(payload["target_path"]),
                safety_backup_path=str(payload["safety_backup_path"]),
                backup_sha256=str(payload["backup_sha256"]),
                backup_size_bytes=int(payload["backup_size_bytes"]),
                backup_schema_version=int(payload["backup_schema_version"]),
                target_size_bytes=int(payload["target_size_bytes"]),
                target_schema_version=int(payload["target_schema_version"]),
                target_mtime_ns=int(payload["target_mtime_ns"]),
                required_free_bytes=int(payload["required_free_bytes"]),
                disk_free_bytes=int(payload["disk_free_bytes"]),
                created_at=str(payload["created_at"]),
                expires_at=str(payload["expires_at"]),
                fingerprint=str(payload["fingerprint"]),
            )
        except (TypeError, ValueError) as exc:
            raise RestorePlanError("restore plan contains invalid field types") from exc


def _confirmation_secret(secret: str | None = None) -> bytes:
    resolved = secret or os.getenv("MEMORY_CONFIRMATION_SECRET") or os.getenv("OWNER_ID")
    if not resolved:
        raise RestorePlanError("MEMORY_CONFIRMATION_SECRET or OWNER_ID is required")
    return resolved.encode("utf-8")


def _canonical_plan_payload(plan: RestorePlan | dict[str, object]) -> str:
    data = plan.to_dict() if isinstance(plan, RestorePlan) else dict(plan)
    data.pop("fingerprint", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_restore_confirmation_token(plan: RestorePlan, *, secret: str | None = None) -> str:
    expected = _fingerprint(_canonical_plan_payload(plan))
    if not plan.fingerprint or not hmac.compare_digest(plan.fingerprint, expected):
        raise RestorePlanError("restore plan fingerprint is invalid")
    signature = hmac.new(_confirmation_secret(secret), expected.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expected}.{signature}"


def validate_restore_confirmation(
    plan: RestorePlan,
    token: str,
    *,
    secret: str | None = None,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    try:
        expires = datetime.fromisoformat(plan.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RestoreConfirmationError("restore plan expiry is invalid") from exc
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires.astimezone(UTC) <= current.astimezone(UTC):
        raise RestoreConfirmationError("restore confirmation plan has expired")
    try:
        token_fingerprint, token_signature = token.split(".", 1)
    except ValueError as exc:
        raise RestoreConfirmationError("invalid restore confirmation token format") from exc
    expected = _fingerprint(_canonical_plan_payload(plan))
    if not hmac.compare_digest(plan.fingerprint, expected):
        raise RestoreConfirmationError("restore plan has changed")
    if not hmac.compare_digest(token_fingerprint, expected):
        raise RestoreConfirmationError("restore token does not match this plan")
    expected_signature = hmac.new(
        _confirmation_secret(secret), expected.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(token_signature, expected_signature):
        raise RestoreConfirmationError("invalid restore confirmation token signature")


class RestoreService:
    """Plan and execute a verified SQLite restore with a mandatory safety backup."""

    def __init__(self, target_path: str | Path) -> None:
        self.target_path = Path(target_path).expanduser().resolve()

    def plan_restore(
        self,
        backup_path: str | Path,
        *,
        confirmation_ttl_seconds: int = DEFAULT_RESTORE_TTL_SECONDS,
        now: datetime | None = None,
    ) -> tuple[RestorePlan, str]:
        if confirmation_ttl_seconds < 1 or confirmation_ttl_seconds > MAX_RESTORE_TTL_SECONDS:
            raise RestorePlanError("confirmation_ttl_seconds must be between 1 and 3600")
        target = self.target_path
        backup = Path(backup_path).expanduser().resolve()
        if not target.is_file():
            raise RestorePlanError("active SQLite database does not exist", path=target)
        if not backup.is_file():
            raise RestorePlanError("restore backup does not exist", path=backup)
        if target == backup:
            raise RestorePlanError("restore backup must differ from the active database", path=backup)

        manifest = verify_backup_manifest(backup)
        backup_schema = self._inspect_database(backup)
        target_schema = self._inspect_database(target, full_integrity=False)
        if backup_schema["integrity"] != "ok":
            raise RestorePlanError("restore backup failed SQLite integrity validation", path=backup)
        if backup_schema["schema_version"] != manifest.schema_version:
            raise RestorePlanError("backup schema version does not match its manifest", path=backup)
        if target_schema["schema_version"] != backup_schema["schema_version"]:
            raise RestorePlanError(
                "backup schema version is incompatible with the active database", path=backup
            )

        target_stat = target.stat()
        required = manifest.backup_size_bytes + target_stat.st_size + max(
            1024 * 1024, manifest.backup_size_bytes // 10
        )
        free = self._disk_free(target.parent)
        if free < required:
            raise RestorePlanError("insufficient disk space for safe restore", path=target.parent)

        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        current = current.astimezone(UTC)
        created_at = current.isoformat()
        expires_at = (current + timedelta(seconds=confirmation_ttl_seconds)).isoformat()
        stamp = current.strftime("%Y%m%dT%H%M%S%fZ")
        safety = target.parent / "backups" / f"pre-restore-{stamp}.db"
        base: dict[str, object] = {
            "backup_path": str(backup),
            "manifest_path": str(manifest_path_for(backup)),
            "target_path": str(target),
            "safety_backup_path": str(safety),
            "backup_sha256": manifest.sha256,
            "backup_size_bytes": manifest.backup_size_bytes,
            "backup_schema_version": manifest.schema_version,
            "target_size_bytes": target_stat.st_size,
            "target_schema_version": int(target_schema["schema_version"]),
            "target_mtime_ns": target_stat.st_mtime_ns,
            "required_free_bytes": required,
            "disk_free_bytes": free,
            "created_at": created_at,
            "expires_at": expires_at,
        }
        fingerprint = _fingerprint(json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        plan = RestorePlan(**base, fingerprint=fingerprint)  # type: ignore[arg-type]
        return plan, create_restore_confirmation_token(plan)

    def execute_restore(self, plan: RestorePlan | dict[str, object], confirmation_token: str) -> dict[str, object]:
        parsed = RestorePlan.from_dict(plan) if isinstance(plan, dict) else plan
        if parsed.fingerprint in _USED_RESTORE_FINGERPRINTS:
            raise RestoreConfirmationError("restore confirmation token has already been used")
        validate_restore_confirmation(parsed, confirmation_token)
        target = Path(parsed.target_path).expanduser().resolve()
        backup = Path(parsed.backup_path).expanduser().resolve()
        if target != self.target_path:
            raise RestorePlanError("restore target does not match the active database")
        self._revalidate_plan(parsed, target, backup)

        safety_path = Path(parsed.safety_backup_path).expanduser().resolve()
        safety = BackupService(target).create_backup(safety_path)
        restore_temp = target.with_name(f".{target.name}.{uuid4().hex}.restore.tmp")
        replaced = False
        try:
            shutil.copyfile(backup, restore_temp)
            if sha256_file(restore_temp) != parsed.backup_sha256:
                raise RestoreExecutionError("temporary restore copy failed SHA-256 verification")
            self._checkpoint_and_clear_sidecars(target)
            os.replace(restore_temp, target)
            replaced = True
            self._validate_restored_target(target, parsed)
        except Exception as exc:
            try:
                restore_temp.unlink(missing_ok=True)
            except OSError:
                pass
            if replaced:
                self._rollback_from_safety_backup(target, safety.backup_path)
            if isinstance(exc, (RestoreExecutionError, RestorePlanError, RestoreConfirmationError)):
                raise
            raise RestoreExecutionError("SQLite restore execution failed", path=target) from exc

        _USED_RESTORE_FINGERPRINTS.add(parsed.fingerprint)
        return {
            "status": "ok",
            "fingerprint": parsed.fingerprint,
            "restored_sha256": parsed.backup_sha256,
            "schema_version": parsed.backup_schema_version,
            "safety_backup_path": str(safety.backup_path),
            "safety_manifest_path": str(safety.manifest_path),
        }

    def _revalidate_plan(self, plan: RestorePlan, target: Path, backup: Path) -> None:
        target_stat = target.stat()
        if target_stat.st_size != plan.target_size_bytes or target_stat.st_mtime_ns != plan.target_mtime_ns:
            raise RestorePlanError("active database changed after restore preview", path=target)
        manifest = verify_backup_manifest(backup, plan.manifest_path)
        if manifest.sha256 != plan.backup_sha256 or manifest.backup_size_bytes != plan.backup_size_bytes:
            raise RestorePlanError("restore backup changed after preview", path=backup)
        backup_info = self._inspect_database(backup)
        if int(backup_info["schema_version"]) != plan.backup_schema_version:
            raise RestorePlanError("restore backup schema changed after preview", path=backup)
        target_info = self._inspect_database(target, full_integrity=False)
        if int(target_info["schema_version"]) != plan.target_schema_version:
            raise RestorePlanError("active database schema changed after preview", path=target)
        if self._disk_free(target.parent) < plan.required_free_bytes:
            raise RestorePlanError("insufficient disk space for safe restore", path=target.parent)

    @staticmethod
    def _inspect_database(path: Path, *, full_integrity: bool = True) -> dict[str, object]:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            integrity = "ok"
            if full_integrity:
                rows = connection.execute("pragma integrity_check").fetchall()
                if [str(row[0]) for row in rows] != ["ok"]:
                    integrity = "failed"
            schema_version = int(connection.execute("pragma user_version").fetchone()[0])
            return {"integrity": integrity, "schema_version": schema_version}
        finally:
            connection.close()

    @staticmethod
    def _disk_free(path: Path) -> int:
        return int(shutil.disk_usage(path).free)

    @staticmethod
    def _checkpoint_and_clear_sidecars(target: Path) -> None:
        connection = sqlite3.connect(target, timeout=0.2)
        try:
            row = connection.execute("pragma wal_checkpoint(truncate)").fetchone()
            if row is not None and int(row[0]) != 0:
                raise RestoreExecutionError("active database is busy; WAL checkpoint could not complete")
        finally:
            connection.close()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{target}{suffix}")
            try:
                sidecar.unlink(missing_ok=True)
            except OSError as exc:
                raise RestoreExecutionError(
                    "active database sidecar is in use; restore aborted", path=sidecar
                ) from exc

    def _validate_restored_target(self, target: Path, plan: RestorePlan) -> None:
        if sha256_file(target) != plan.backup_sha256:
            raise RestoreExecutionError("restored database SHA-256 does not match the verified backup")
        info = self._inspect_database(target)
        if info["integrity"] != "ok" or int(info["schema_version"]) != plan.backup_schema_version:
            raise RestoreExecutionError("restored database failed post-restore validation")

    def _rollback_from_safety_backup(self, target: Path, safety_backup: Path) -> None:
        verify_backup_manifest(safety_backup)
        rollback_temp = target.with_name(f".{target.name}.{uuid4().hex}.rollback.tmp")
        try:
            shutil.copyfile(safety_backup, rollback_temp)
            self._checkpoint_and_clear_sidecars(target)
            os.replace(rollback_temp, target)
            info = self._inspect_database(target)
            if info["integrity"] != "ok":
                raise RestoreExecutionError("automatic rollback failed integrity validation")
        except Exception as exc:
            try:
                rollback_temp.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, RestoreExecutionError):
                raise
            raise RestoreExecutionError("automatic rollback after restore failure failed", path=target) from exc
