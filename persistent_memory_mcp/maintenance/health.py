"""Read-only SQLite health and integrity diagnostics."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .errors import BackupError, HealthError
from .manifest import BackupManifest, load_backup_manifest, verify_backup_manifest

_EXPECTED_INDEXES = frozenset(
    {
        "idx_projects_owner_slug",
        "idx_decisions_scope",
        "idx_tasks_scope",
        "idx_sessions_scope",
        "idx_warnings_scope",
        "idx_memory_documents_scope",
        "idx_timeline_scope",
    }
)
_MAX_DIAGNOSTIC_ROWS = 100
_MAX_MANIFEST_CANDIDATES = 200


@dataclass(frozen=True)
class HealthResult:
    """Bounded, serialization-friendly health report for one local database."""

    status: str
    database_name: str
    sqlite_version: str
    schema_version: int
    journal_mode: str
    database_size_bytes: int
    wal_size_bytes: int
    shm_size_bytes: int
    disk_free_bytes: int
    quick_check: tuple[str, ...]
    integrity_check: tuple[str, ...] | None
    foreign_key_violations: tuple[dict[str, object], ...]
    foreign_key_violations_truncated: bool
    expected_indexes: tuple[str, ...]
    missing_indexes: tuple[str, ...]
    latest_verified_backup: dict[str, object] | None
    invalid_backup_manifests: int
    maintenance_ready: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "database_name": self.database_name,
            "sqlite_version": self.sqlite_version,
            "schema_version": self.schema_version,
            "journal_mode": self.journal_mode,
            "database_size_bytes": self.database_size_bytes,
            "wal_size_bytes": self.wal_size_bytes,
            "shm_size_bytes": self.shm_size_bytes,
            "disk_free_bytes": self.disk_free_bytes,
            "quick_check": list(self.quick_check),
            "integrity_check": list(self.integrity_check) if self.integrity_check is not None else None,
            "foreign_key_violations": list(self.foreign_key_violations),
            "foreign_key_violations_truncated": self.foreign_key_violations_truncated,
            "expected_indexes": list(self.expected_indexes),
            "missing_indexes": list(self.missing_indexes),
            "latest_verified_backup": self.latest_verified_backup,
            "invalid_backup_manifests": self.invalid_backup_manifests,
            "maintenance_ready": self.maintenance_ready,
        }


class HealthService:
    """Inspect an existing SQLite database without mutating application data."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        backup_directory: str | Path | None = None,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.backup_directory = (
            Path(backup_directory).expanduser().resolve() if backup_directory is not None else None
        )

    def check(self, *, full_integrity: bool = False) -> HealthResult:
        path = self.database_path
        if not path.exists() or not path.is_file():
            raise HealthError("Local SQLite database does not exist.", path=path)

        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            try:
                connection.execute("pragma foreign_keys = on")
                quick = self._check_rows(connection, "pragma quick_check")
                full = (
                    self._check_rows(connection, "pragma integrity_check")
                    if full_integrity
                    else None
                )
                sqlite_version = str(connection.execute("select sqlite_version()").fetchone()[0])
                schema_version = int(connection.execute("pragma user_version").fetchone()[0])
                journal_mode = str(connection.execute("pragma journal_mode").fetchone()[0])
                foreign_rows, foreign_truncated = self._foreign_key_rows(connection)
                index_rows = connection.execute(
                    "select name from sqlite_master where type = 'index' and name is not null"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise HealthError("SQLite health checks could not be completed.", path=path) from exc

        present_indexes = {str(row[0]) for row in index_rows}
        missing_indexes = tuple(sorted(_EXPECTED_INDEXES - present_indexes))
        latest_backup, invalid_manifests = self._latest_verified_backup()
        quick_ok = quick == ("ok",)
        full_ok = full is None or full == ("ok",)
        db_healthy = quick_ok and full_ok and not foreign_rows and not missing_indexes
        status = "healthy" if db_healthy else "degraded"
        maintenance_ready = db_healthy and latest_backup is not None

        return HealthResult(
            status=status,
            database_name=path.name,
            sqlite_version=sqlite_version,
            schema_version=schema_version,
            journal_mode=journal_mode,
            database_size_bytes=path.stat().st_size,
            wal_size_bytes=self._sidecar_size(path, "-wal"),
            shm_size_bytes=self._sidecar_size(path, "-shm"),
            disk_free_bytes=shutil.disk_usage(path.parent).free,
            quick_check=quick,
            integrity_check=full,
            foreign_key_violations=foreign_rows,
            foreign_key_violations_truncated=foreign_truncated,
            expected_indexes=tuple(sorted(_EXPECTED_INDEXES)),
            missing_indexes=missing_indexes,
            latest_verified_backup=latest_backup,
            invalid_backup_manifests=invalid_manifests,
            maintenance_ready=maintenance_ready,
        )

    @staticmethod
    def _check_rows(connection: sqlite3.Connection, pragma: str) -> tuple[str, ...]:
        cursor = connection.execute(pragma)
        rows = cursor.fetchmany(_MAX_DIAGNOSTIC_ROWS + 1)
        values = tuple(str(row[0]) for row in rows[:_MAX_DIAGNOSTIC_ROWS])
        if len(rows) > _MAX_DIAGNOSTIC_ROWS:
            return values + ("diagnostic output truncated",)
        return values

    @staticmethod
    def _foreign_key_rows(
        connection: sqlite3.Connection,
    ) -> tuple[tuple[dict[str, object], ...], bool]:
        rows = connection.execute("pragma foreign_key_check").fetchmany(_MAX_DIAGNOSTIC_ROWS + 1)
        truncated = len(rows) > _MAX_DIAGNOSTIC_ROWS
        result = tuple(
            {
                "table": str(row[0]),
                "rowid": row[1],
                "parent": str(row[2]),
                "foreign_key_id": int(row[3]),
            }
            for row in rows[:_MAX_DIAGNOSTIC_ROWS]
        )
        return result, truncated

    @staticmethod
    def _sidecar_size(path: Path, suffix: str) -> int:
        sidecar = Path(f"{path}{suffix}")
        try:
            return sidecar.stat().st_size
        except OSError:
            return 0

    def _latest_verified_backup(self) -> tuple[dict[str, object] | None, int]:
        directory = self.backup_directory
        if directory is None or not directory.is_dir():
            return None, 0

        candidates = sorted(
            directory.glob("*.manifest.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:_MAX_MANIFEST_CANDIDATES]
        verified: list[BackupManifest] = []
        invalid = 0
        for manifest_path in candidates:
            try:
                manifest = load_backup_manifest(manifest_path)
                backup_path = manifest_path.parent / manifest.backup_name
                verified.append(verify_backup_manifest(backup_path, manifest_path))
            except (BackupError, OSError):
                invalid += 1
        if not verified:
            return None, invalid
        latest = max(verified, key=lambda manifest: manifest.created_at)
        return {
            "backup_name": latest.backup_name,
            "created_at": latest.created_at,
            "backup_size_bytes": latest.backup_size_bytes,
            "sha256": latest.sha256,
            "schema_version": latest.schema_version,
            "integrity_status": latest.integrity_status,
        }, invalid
