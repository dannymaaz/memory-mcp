"""Backup-first, checksum-verified SQLite migrations for safe local upgrades."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping

from .maintenance.backup_service import BackupService
from .sqlite_migrations import MIGRATIONS

_REQUIRED_TABLES = frozenset(
    {"workspaces", "projects", "decisions", "tasks", "sessions", "warnings"}
)
_TRANSACTION_CONTROL = frozenset({"begin", "commit", "rollback", "savepoint", "release"})


class MigrationError(RuntimeError):
    """Base error for local SQLite migration failures."""


class MigrationChecksumError(MigrationError):
    """Raised when an already-applied migration no longer matches its checksum."""


class MigrationCompatibilityError(MigrationError):
    """Raised when the database or migration set is unsafe to upgrade."""


class MigrationExecutionError(MigrationError):
    """Raised when a migration fails while being applied."""


@dataclass(frozen=True)
class MigrationPlan:
    """Read-only description of the current and pending local schema state."""

    schema_version: int
    pending: tuple[dict[str, object], ...]
    applied: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "pending": list(self.pending),
            "applied": list(self.applied),
            "backup_required": bool(self.pending),
        }


@dataclass(frozen=True)
class _Migration:
    version: int
    name: str
    sql: str
    checksum: str


class MigrationService:
    """Plan and apply ordered SQLite migrations after creating a verified backup."""

    def __init__(
        self,
        database_path: str | Path,
        migrations: Iterable[Mapping[str, object]] = MIGRATIONS,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.migrations = self._normalize_migrations(migrations)

    @staticmethod
    def _checksum(sql: str) -> str:
        return hashlib.sha256(sql.encode("utf-8")).hexdigest()

    @classmethod
    def _normalize_migrations(
        cls,
        migrations: Iterable[Mapping[str, object]],
    ) -> tuple[_Migration, ...]:
        normalized: list[_Migration] = []
        versions: set[int] = set()
        for raw in migrations:
            try:
                version = int(raw["version"])
                name = str(raw["name"]).strip()
                sql = str(raw["sql"]).strip()
            except (KeyError, TypeError, ValueError) as exc:
                raise MigrationCompatibilityError("migration metadata is invalid") from exc
            if version < 1:
                raise MigrationCompatibilityError("migration versions must be positive integers")
            if version in versions:
                raise MigrationCompatibilityError(f"duplicate migration version: {version}")
            if not name or not sql:
                raise MigrationCompatibilityError("migration name and SQL must not be empty")
            cls._reject_transaction_control(sql, version, name)
            versions.add(version)
            normalized.append(_Migration(version, name, sql, cls._checksum(sql)))
        normalized.sort(key=lambda migration: migration.version)
        if not normalized:
            raise MigrationCompatibilityError("at least one SQLite migration is required")
        return tuple(normalized)

    @staticmethod
    def _reject_transaction_control(sql: str, version: int, name: str) -> None:
        tokens = sql.lower().replace(";", " ").split()
        if _TRANSACTION_CONTROL.intersection(tokens):
            raise MigrationCompatibilityError(
                f"migration {version:04d}_{name} must not manage transactions explicitly"
            )

    def _validate_database(self) -> None:
        if not self.database_path.is_file():
            raise MigrationCompatibilityError("SQLite database does not exist")
        connection: sqlite3.Connection | None = None
        try:
            uri = f"file:{self.database_path.as_posix()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            quick_check = connection.execute("pragma quick_check").fetchone()
            if quick_check is None or str(quick_check[0]) != "ok":
                raise MigrationCompatibilityError("SQLite quick_check failed")
            tables = {
                str(row[0])
                for row in connection.execute(
                    "select name from sqlite_master "
                    "where type='table' and name not like 'sqlite_%'"
                )
            }
        except sqlite3.Error as exc:
            raise MigrationCompatibilityError("SQLite database could not be inspected") from exc
        finally:
            if connection is not None:
                connection.close()

        missing = sorted(_REQUIRED_TABLES - tables)
        if missing:
            raise MigrationCompatibilityError(
                "missing required v0.2 tables: " + ", ".join(missing)
            )

    def plan(self) -> MigrationPlan:
        """Inspect migration state without mutating the database."""
        self._validate_database()
        connection: sqlite3.Connection | None = None
        try:
            uri = f"file:{self.database_path.as_posix()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            schema_version = int(connection.execute("pragma user_version").fetchone()[0])
            tracking_exists = connection.execute(
                "select 1 from sqlite_master "
                "where type='table' and name='schema_migrations'"
            ).fetchone()
            applied_rows = (
                connection.execute(
                    "select version, name, checksum, applied_at "
                    "from schema_migrations order by version"
                ).fetchall()
                if tracking_exists
                else []
            )
        except sqlite3.Error as exc:
            raise MigrationCompatibilityError("migration history could not be inspected") from exc
        finally:
            if connection is not None:
                connection.close()

        latest_supported = self.migrations[-1].version
        if schema_version > latest_supported:
            raise MigrationCompatibilityError(
                f"database schema version {schema_version} is newer than supported "
                f"version {latest_supported}"
            )

        applied_by_version = {int(row[0]): row for row in applied_rows}
        if applied_by_version and max(applied_by_version) > schema_version:
            raise MigrationCompatibilityError(
                "migration history is ahead of SQLite user_version"
            )

        pending: list[dict[str, object]] = []
        for migration in self.migrations:
            applied = applied_by_version.get(migration.version)
            if applied is not None:
                if str(applied[1]) != migration.name:
                    raise MigrationCompatibilityError(
                        f"applied migration {migration.version:04d} name changed"
                    )
                if str(applied[2]) != migration.checksum:
                    raise MigrationChecksumError(
                        f"applied migration {migration.version:04d}_{migration.name} "
                        "checksum changed"
                    )
                continue
            if migration.version <= schema_version:
                raise MigrationCompatibilityError(
                    f"schema version {schema_version} indicates migration "
                    f"{migration.version:04d}_{migration.name} is applied, but history is missing"
                )
            pending.append(
                {
                    "version": migration.version,
                    "name": migration.name,
                    "checksum": migration.checksum,
                }
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
        return MigrationPlan(schema_version, tuple(pending), applied)

    def bootstrap_fresh_database(self) -> MigrationPlan:
        """Record packaged schema history for a newly created, still-empty database.

        This is deliberately different from upgrading an existing database: migration
        SQL is not replayed because ``sqlite_schema.sql`` already represents the current
        packaged schema. The operation refuses any database containing user rows or
        prior version/history state, so an old installation cannot be marked current.
        """
        self._validate_database()
        connection = sqlite3.connect(self.database_path)
        try:
            schema_version = int(connection.execute("pragma user_version").fetchone()[0])
            if schema_version != 0:
                raise MigrationCompatibilityError(
                    "fresh database bootstrap requires PRAGMA user_version = 0"
                )

            tables = [
                str(row[0])
                for row in connection.execute(
                    "select name from sqlite_master "
                    "where type='table' and name not like 'sqlite_%' order by name"
                ).fetchall()
            ]
            non_empty: list[str] = []
            for table in tables:
                if table == "schema_migrations":
                    continue
                quoted = table.replace('"', '""')
                row = connection.execute(
                    f'SELECT 1 FROM "{quoted}" LIMIT 1'
                ).fetchone()
                if row is not None:
                    non_empty.append(table)
            if non_empty:
                raise MigrationCompatibilityError(
                    "fresh database bootstrap refused because data already exists in: "
                    + ", ".join(non_empty)
                )

            tracking_exists = "schema_migrations" in tables
            if tracking_exists:
                history = connection.execute(
                    "select version, name, checksum from schema_migrations order by version"
                ).fetchall()
                if history:
                    raise MigrationCompatibilityError(
                        "fresh database bootstrap refused because migration history already exists"
                    )
            else:
                connection.execute(
                    "create table schema_migrations ("
                    "version integer primary key, "
                    "name text not null, "
                    "checksum text not null, "
                    "applied_at text not null)"
                )

            applied_at = datetime.now(UTC).isoformat()
            for migration in self.migrations:
                connection.execute(
                    "insert into schema_migrations "
                    "(version, name, checksum, applied_at) values (?, ?, ?, ?)",
                    (migration.version, migration.name, migration.checksum, applied_at),
                )
            connection.execute(f"pragma user_version = {self.migrations[-1].version}")
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise MigrationExecutionError("fresh SQLite schema bootstrap failed") from exc
        finally:
            connection.close()

        plan = self.plan()
        if plan.pending:
            raise MigrationExecutionError("fresh SQLite schema bootstrap left pending migrations")
        return plan

    def apply(self, backup_directory: str | Path) -> dict[str, object]:
        """Apply all pending migrations after a verified pre-migration backup."""
        plan = self.plan()
        if not plan.pending:
            return {
                "status": "current",
                "plan": plan.as_dict(),
                "applied": [],
                "backup": None,
            }

        backup_directory = Path(backup_directory).expanduser().resolve()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = BackupService(self.database_path).create_backup(
            backup_directory / f"pre-migration-{stamp}.db"
        )

        tracking_connection = sqlite3.connect(self.database_path)
        try:
            tracking_connection.execute(
                "create table if not exists schema_migrations ("
                "version integer primary key, "
                "name text not null, "
                "checksum text not null, "
                "applied_at text not null)"
            )
            tracking_connection.commit()
        finally:
            tracking_connection.close()

        by_version = {migration.version: migration for migration in self.migrations}
        applied_now: list[dict[str, object]] = []
        for item in plan.pending:
            migration = by_version[int(item["version"])]
            connection = sqlite3.connect(self.database_path)
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + migration.sql + "\n")
                connection.execute(
                    "insert into schema_migrations "
                    "(version, name, checksum, applied_at) values (?, ?, ?, ?)",
                    (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                connection.commit()
                applied_now.append(item)
            except sqlite3.Error as exc:
                connection.rollback()
                raise MigrationExecutionError(
                    f"migration {migration.version:04d}_{migration.name} failed"
                ) from exc
            finally:
                connection.close()

        return {
            "status": "ok",
            "applied": applied_now,
            "backup": backup.as_dict(),
            "plan": self.plan().as_dict(),
        }
