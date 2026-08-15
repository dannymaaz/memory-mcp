"""Typed errors for local maintenance operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class MaintenanceError(RuntimeError):
    """Base error with a stable machine-readable code."""

    code = "maintenance_error"

    def __init__(self, message: str, *, path: str | Path | None = None) -> None:
        super().__init__(message)
        self.path = str(path) if path is not None else None

    def as_dict(self) -> dict[str, Any]:
        """Return bounded error metadata without database contents."""
        payload: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.path is not None:
            payload["path"] = self.path
        return payload


class BackupError(MaintenanceError):
    code = "backup_error"


class BackupSourceError(BackupError):
    code = "backup_source_error"


class BackupDestinationError(BackupError):
    code = "backup_destination_error"


class BackupIntegrityError(BackupError):
    code = "backup_integrity_error"


class BackupManifestError(BackupError):
    code = "backup_manifest_error"


class BackupVerificationError(BackupError):
    code = "backup_verification_error"


class HealthError(MaintenanceError):
    code = "health_error"


class MigrationError(MaintenanceError):
    """Base error for local SQLite migrations."""

    code = "migration_error"


class MigrationChecksumError(MigrationError):
    code = "migration_checksum_error"


class MigrationCompatibilityError(MigrationError):
    code = "migration_compatibility_error"


class MigrationExecutionError(MigrationError):
    code = "migration_execution_error"
