"""Safe local maintenance services for Persistent Memory MCP."""

from .backup_service import BackupResult, BackupService
from .errors import (
    BackupDestinationError,
    BackupError,
    BackupIntegrityError,
    BackupManifestError,
    BackupSourceError,
    BackupVerificationError,
    HealthError,
    MaintenanceError,
    MigrationChecksumError,
    MigrationCompatibilityError,
    MigrationError,
    MigrationExecutionError,
)
from .health import HealthResult, HealthService
from .manifest import (
    BackupManifest,
    load_backup_manifest,
    manifest_path_for,
    sha256_file,
    verify_backup_manifest,
)
from .migrations import Migration, MigrationPlan, MigrationService

__all__ = [
    "BackupDestinationError",
    "BackupError",
    "BackupIntegrityError",
    "BackupManifest",
    "BackupManifestError",
    "BackupResult",
    "BackupService",
    "BackupSourceError",
    "BackupVerificationError",
    "HealthError",
    "HealthResult",
    "HealthService",
    "MaintenanceError",
    "Migration",
    "MigrationChecksumError",
    "MigrationCompatibilityError",
    "MigrationError",
    "MigrationExecutionError",
    "MigrationPlan",
    "MigrationService",
    "load_backup_manifest",
    "manifest_path_for",
    "sha256_file",
    "verify_backup_manifest",
]
