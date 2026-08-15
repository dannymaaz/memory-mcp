"""Consistent and verified SQLite backup creation."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import BackupDestinationError, BackupError, BackupIntegrityError, BackupSourceError
from .manifest import manifest_path_for, write_backup_manifest


@dataclass(frozen=True)
class BackupResult:
    """Bounded metadata describing a completed SQLite backup."""

    backup_path: Path
    manifest_path: Path
    created_at: datetime
    source_size_bytes: int
    backup_size_bytes: int
    sha256: str
    sqlite_version: str
    schema_version: int
    integrity_status: str
    table_counts: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        """Return serialization-friendly metadata without stored memory values."""
        return {
            "backup_path": str(self.backup_path),
            "manifest_path": str(self.manifest_path),
            "created_at": self.created_at.isoformat(),
            "source_size_bytes": self.source_size_bytes,
            "backup_size_bytes": self.backup_size_bytes,
            "sha256": self.sha256,
            "sqlite_version": self.sqlite_version,
            "schema_version": self.schema_version,
            "integrity_status": self.integrity_status,
            "table_counts": dict(self.table_counts),
        }


class BackupService:
    """Create verified backups without copying the live SQLite file directly."""

    def __init__(self, source_path: str | Path) -> None:
        self.source_path = Path(source_path).expanduser().resolve()

    def create_backup(self, destination: str | Path) -> BackupResult:
        """Create and validate a backup, refusing overwrite by default."""
        source = self.source_path
        target = Path(destination).expanduser().resolve()
        self._validate_paths(source, target)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupDestinationError(
                "Unable to prepare the backup destination directory.", path=target.parent
            ) from exc

        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        published = False
        try:
            self._copy_database(source, temporary)
            metadata = self._inspect_backup(temporary)
            if target.exists():
                raise BackupDestinationError(
                    "Backup destination already exists; overwrite is not allowed.", path=target
                )
            self._publish_backup(temporary, target)
            published = True
            created_at = datetime.now(UTC)
            manifest = write_backup_manifest(
                target,
                created_at=created_at.isoformat(),
                sqlite_version=str(metadata["sqlite_version"]),
                schema_version=int(metadata["schema_version"]),
                integrity_status=str(metadata["integrity_status"]),
                table_counts=dict(metadata["table_counts"]),
            )
            return BackupResult(
                backup_path=target,
                manifest_path=manifest_path_for(target),
                created_at=created_at,
                source_size_bytes=source.stat().st_size,
                backup_size_bytes=target.stat().st_size,
                sha256=manifest.sha256,
                sqlite_version=str(metadata["sqlite_version"]),
                schema_version=int(metadata["schema_version"]),
                integrity_status=str(metadata["integrity_status"]),
                table_counts=dict(metadata["table_counts"]),
            )
        except BackupError:
            self._cleanup_temporary(temporary)
            if published:
                self._cleanup_published(target)
            raise
        except (OSError, sqlite3.Error) as exc:
            self._cleanup_temporary(temporary)
            if published:
                self._cleanup_published(target)
            raise BackupError("SQLite backup creation failed.", path=target) from exc
        except Exception:
            self._cleanup_temporary(temporary)
            if published:
                self._cleanup_published(target)
            raise

    @staticmethod
    def _validate_paths(source: Path, target: Path) -> None:
        if not source.exists():
            raise BackupSourceError("Source SQLite database does not exist.", path=source)
        if not source.is_file():
            raise BackupSourceError("Source SQLite database is not a file.", path=source)
        if source == target:
            raise BackupDestinationError(
                "Backup destination must differ from the active database.", path=target
            )
        if target.exists():
            raise BackupDestinationError(
                "Backup destination already exists; overwrite is not allowed.", path=target
            )
        manifest_path = manifest_path_for(target)
        if manifest_path.exists():
            raise BackupDestinationError(
                "Backup manifest destination already exists; overwrite is not allowed.",
                path=manifest_path,
            )

    @staticmethod
    def _copy_database(source: Path, temporary: Path) -> None:
        source_connection = sqlite3.connect(source)
        destination_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()

    @staticmethod
    def _inspect_backup(path: Path) -> dict[str, object]:
        connection = sqlite3.connect(path)
        try:
            integrity_rows = connection.execute("pragma integrity_check").fetchall()
            integrity_values = [str(row[0]) for row in integrity_rows]
            if integrity_values != ["ok"]:
                raise BackupIntegrityError("Backup failed SQLite integrity validation.", path=path)

            sqlite_version = str(connection.execute("select sqlite_version()").fetchone()[0])
            schema_version = int(connection.execute("pragma user_version").fetchone()[0])
            table_rows = connection.execute(
                "select name from sqlite_master "
                "where type = 'table' and name not like 'sqlite_%' order by name"
            ).fetchall()
            table_counts: dict[str, int] = {}
            for (table_name,) in table_rows:
                safe_name = str(table_name).replace('"', '""')
                count = int(connection.execute(f'select count(*) from "{safe_name}"').fetchone()[0])
                table_counts[str(table_name)] = count
            return {
                "sqlite_version": sqlite_version,
                "schema_version": schema_version,
                "integrity_status": "ok",
                "table_counts": table_counts,
            }
        finally:
            connection.close()

    @staticmethod
    def _publish_backup(temporary: Path, target: Path) -> None:
        """Publish the completed temporary file without silently clobbering a target."""
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise BackupDestinationError(
                "Backup destination already exists; overwrite is not allowed.", path=target
            ) from exc
        except OSError:
            if target.exists():
                raise BackupDestinationError(
                    "Backup destination already exists; overwrite is not allowed.", path=target
                )
            temporary.replace(target)
            return
        temporary.unlink()

    @staticmethod
    def _cleanup_temporary(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _cleanup_published(path: Path) -> None:
        for candidate in (path, manifest_path_for(path)):
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
