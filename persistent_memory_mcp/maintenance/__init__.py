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
    RestoreConfirmationError,
    RestoreError,
    RestoreExecutionError,
    RestorePlanError,
)
from .health import HealthResult, HealthService
from .manifest import (
    BackupManifest,
    load_backup_manifest,
    manifest_path_for,
    sha256_file,
    verify_backup_manifest,
)
from .restore import (
    RestorePlan,
    RestoreService,
    create_restore_confirmation_token,
    validate_restore_confirmation,
)

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
    "RestoreConfirmationError",
    "RestoreError",
    "RestoreExecutionError",
    "RestorePlan",
    "RestorePlanError",
    "RestoreService",
    "create_restore_confirmation_token",
    "load_backup_manifest",
    "manifest_path_for",
    "sha256_file",
    "validate_restore_confirmation",
    "verify_backup_manifest",
]
