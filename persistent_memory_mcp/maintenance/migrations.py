"""Checksum-verified, backup-first local SQLite migrations."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .backup_service import BackupService
from .errors import MigrationChecksumError, MigrationCompatibilityError, MigrationExecutionError

_MIGRATION_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
_REQUIRED_TABLES = frozenset({"workspaces", "projects", "decisions", "tasks", "sessions", "warnings"})


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class MigrationPlan:
    current_schema_version: int
    pending: tuple[dict[str, object], ...]
    applied: tuple[dict[str, object], ...]
    backup_required: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "current_schema_version": self.current_schema_version,
            "pending": list(self.pending),
            "applied": list(self.applied),
            "backup_required": self.backup_required,
        }


class MigrationService:
    """Plan and apply ordered local migrations with checksums and a verified backup."""

    def __init__(self, database_path: str | Path, migration_dir: str | Path | None = None) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.migration_dir = (
            Path(migration_dir).expanduser().resolve()
            if migration_dir is not None
            else Path(__file__).parent.parent / "sqlite_migrations"
        )

    def plan(self) -> MigrationPlan:
        self._validate_database()
        migrations = self._load_migrations()
        with sqlite3.connect(self.database_path) as connection:
            self._ensure_tracking_table(connection)
            applied_rows = connection.execute(
                "select version, name, checksum, applied_at from schema_migrations order by version"
            ).fetchall()
            current_schema_version = int(connection.execute("pragma user_version").fetchone()[0])
        applied_by_version = {int(row[0]): row for row in applied_rows}
        for migration in migrations:
            if migration.version in applied_by_version:
                row = applied_by_version[migration.version]
                if str(row[2]) != migration.checksum:
                    raise MigrationChecksumError(
                        f"applied migration {migration.version:04d}_{migration.name} checksum changed",
                        path=migration.path,
                    )
        pending = tuple(
            {"version": migration.version, "name": migration.name, "checksum": migration.checksum}
            for migration in migrations
            if migration.version not in applied_by_version
        )
        applied = tuple(
            {
                "version": int(row[0]),
                "name": str(row[1]),
                "checksum": str(row[2]),
                "applied_at": str(row[3]),
            }
            for row in applied_rows
        )
        return MigrationPlan(current_schema_version, pending, applied, bool(pending))

    def apply(self, backup_directory: str | Path) -> dict[str, object]:
        plan = self.plan()
        if not plan.pending:
            return {"status": "current", "plan": plan.as_dict(), "applied": [], "backup": None}
        backup_dir = Path(backup_directory).expanduser().resolve()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = BackupService(self.database_path).create_backup(
            backup_dir / f"pre-migration-{stamp}.db"
        )
        migrations = {migration.version: migration for migration in self._load_migrations()}
        applied_now: list[dict[str, object]] = []
        try:
            for item in plan.pending:
                migration = migrations[int(item["version"])]
                self._apply_one(migration)
                applied_now.append(
                    {"version": migration.version, "name": migration.name, "checksum": migration.checksum}
                )
        except Exception as exc:
            if isinstance(exc, (MigrationChecksumError, MigrationCompatibilityError, MigrationExecutionError)):
                raise
            raise MigrationExecutionError("SQLite migration failed", path=self.database_path) from exc
        return {
            "status": "ok",
            "applied": applied_now,
            "backup": backup.as_dict(),
            "plan": self.plan().as_dict(),
        }

    def _validate_database(self) -> None:
        if not self.database_path.is_file():
            raise MigrationCompatibilityError("SQLite database does not exist", path=self.database_path)
        try:
            with sqlite3.connect(self.database_path) as connection:
                integrity = connection.execute("pragma quick_check").fetchone()[0]
                if str(integrity) != "ok":
                    raise MigrationCompatibilityError("SQLite database failed quick_check")
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
                    ).fetchall()
                }
        except sqlite3.Error as exc:
            raise MigrationCompatibilityError("SQLite database could not be inspected") from exc
        missing = sorted(_REQUIRED_TABLES - tables)
        if missing:
            raise MigrationCompatibilityError(
                f"database is missing required v0.2 tables: {', '.join(missing)}"
            )

    def _load_migrations(self) -> tuple[Migration, ...]:
        if not self.migration_dir.is_dir():
            raise MigrationCompatibilityError("SQLite migration directory is missing", path=self.migration_dir)
        result: list[Migration] = []
        versions: set[int] = set()
        for path in sorted(self.migration_dir.glob("*.sql")):
            match = _MIGRATION_RE.fullmatch(path.name)
            if not match:
                raise MigrationCompatibilityError(f"invalid migration filename: {path.name}", path=path)
            version = int(match.group(1))
            if version in versions:
                raise MigrationCompatibilityError(f"duplicate migration version: {version}")
            versions.add(version)
            sql = path.read_text(encoding="utf-8")
            result.append(
                Migration(version, match.group(2), path, hashlib.sha256(sql.encode("utf-8")).hexdigest(), sql)
            )
        if not result:
            raise MigrationCompatibilityError("no SQLite migrations were found", path=self.migration_dir)
        return tuple(result)

    @staticmethod
    def _ensure_tracking_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            "create table if not exists schema_migrations ("
            "version integer primary key, name text not null, checksum text not null, "
            "applied_at text not null)"
        )
        connection.commit()

    def _apply_one(self, migration: Migration) -> None:
        applied_at = datetime.now(UTC).isoformat()
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + migration.sql + "\n")
            connection.execute(
                "insert into schema_migrations (version, name, checksum, applied_at) values (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, applied_at),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise MigrationExecutionError(
                f"migration {migration.version:04d}_{migration.name} failed", path=migration.path
            ) from exc
        finally:
            connection.close()
