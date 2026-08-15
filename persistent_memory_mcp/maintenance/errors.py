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
    """Base error for backup creation failures."""

    code = "backup_error"


class BackupSourceError(BackupError):
    """Raised when the source database cannot be used safely."""

    code = "backup_source_error"


class BackupDestinationError(BackupError):
    """Raised when the requested destination is unsafe or unavailable."""

    code = "backup_destination_error"


class BackupIntegrityError(BackupError):
    """Raised when the completed backup fails SQLite integrity validation."""

    code = "backup_integrity_error"


class BackupManifestError(BackupError):
    """Raised when backup manifest metadata is missing or malformed."""

    code = "backup_manifest_error"


class BackupVerificationError(BackupError):
    """Raised when a backup no longer matches its verification manifest."""

    code = "backup_verification_error"
