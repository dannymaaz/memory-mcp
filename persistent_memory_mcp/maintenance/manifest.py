"""Versioned SHA-256 manifests for verified SQLite backups."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from .errors import BackupManifestError, BackupVerificationError

MANIFEST_FORMAT_VERSION = 1
_HASH_CHUNK_SIZE = 1024 * 1024


def _package_version() -> str:
    try:
        return version("persistent-memory-mcp")
    except PackageNotFoundError:  # pragma: no cover - editable/source fallback
        return "0+unknown"


def manifest_path_for(backup_path: str | Path) -> Path:
    backup = Path(backup_path).expanduser().resolve()
    return backup.with_name(f"{backup.name}.manifest.json")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class BackupManifest:
    format_version: int
    package_version: str
    created_at: str
    backup_name: str
    backup_size_bytes: int
    sha256: str
    sqlite_version: str
    schema_version: int
    integrity_status: str
    table_counts: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "format_version": self.format_version,
            "package_version": self.package_version,
            "created_at": self.created_at,
            "backup_name": self.backup_name,
            "backup_size_bytes": self.backup_size_bytes,
            "sha256": self.sha256,
            "sqlite_version": self.sqlite_version,
            "schema_version": self.schema_version,
            "integrity_status": self.integrity_status,
            "table_counts": dict(self.table_counts),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "BackupManifest":
        required = {
            "format_version",
            "package_version",
            "created_at",
            "backup_name",
            "backup_size_bytes",
            "sha256",
            "sqlite_version",
            "schema_version",
            "integrity_status",
            "table_counts",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise BackupManifestError(f"Backup manifest is missing fields: {', '.join(missing)}")
        try:
            table_counts_raw = payload["table_counts"]
            if not isinstance(table_counts_raw, dict):
                raise TypeError("table_counts must be an object")
            table_counts = {str(key): int(value) for key, value in table_counts_raw.items()}
            manifest = cls(
                format_version=int(payload["format_version"]),
                package_version=str(payload["package_version"]),
                created_at=str(payload["created_at"]),
                backup_name=str(payload["backup_name"]),
                backup_size_bytes=int(payload["backup_size_bytes"]),
                sha256=str(payload["sha256"]),
                sqlite_version=str(payload["sqlite_version"]),
                schema_version=int(payload["schema_version"]),
                integrity_status=str(payload["integrity_status"]),
                table_counts=table_counts,
            )
        except (TypeError, ValueError) as exc:
            raise BackupManifestError("Backup manifest contains invalid field types.") from exc
        if manifest.format_version != MANIFEST_FORMAT_VERSION:
            raise BackupManifestError(
                f"Unsupported backup manifest version: {manifest.format_version}"
            )
        if len(manifest.sha256) != 64 or any(c not in "0123456789abcdef" for c in manifest.sha256):
            raise BackupManifestError("Backup manifest contains an invalid SHA-256 digest.")
        return manifest


def write_backup_manifest(
    backup_path: str | Path,
    *,
    created_at: str,
    sqlite_version: str,
    schema_version: int,
    integrity_status: str,
    table_counts: dict[str, int],
) -> BackupManifest:
    backup = Path(backup_path).expanduser().resolve()
    if not backup.is_file():
        raise BackupManifestError("Backup file does not exist.", path=backup)
    manifest_path = manifest_path_for(backup)
    if manifest_path.exists():
        raise BackupManifestError("Backup manifest already exists.", path=manifest_path)

    manifest = BackupManifest(
        format_version=MANIFEST_FORMAT_VERSION,
        package_version=_package_version(),
        created_at=created_at,
        backup_name=backup.name,
        backup_size_bytes=backup.stat().st_size,
        sha256=sha256_file(backup),
        sqlite_version=sqlite_version,
        schema_version=schema_version,
        integrity_status=integrity_status,
        table_counts=dict(sorted(table_counts.items())),
    )
    temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            os.link(temporary, manifest_path)
        except FileExistsError as exc:
            raise BackupManifestError("Backup manifest already exists.", path=manifest_path) from exc
        except OSError:
            if manifest_path.exists():
                raise BackupManifestError("Backup manifest already exists.", path=manifest_path)
            temporary.replace(manifest_path)
            return manifest
        temporary.unlink()
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def load_backup_manifest(path: str | Path) -> BackupManifest:
    manifest_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupManifestError("Backup manifest could not be read.", path=manifest_path) from exc
    if not isinstance(payload, dict):
        raise BackupManifestError("Backup manifest must be a JSON object.", path=manifest_path)
    try:
        return BackupManifest.from_dict(payload)
    except BackupManifestError as exc:
        if exc.path is None:
            exc.path = str(manifest_path)
        raise


def verify_backup_manifest(
    backup_path: str | Path, manifest_path: str | Path | None = None
) -> BackupManifest:
    backup = Path(backup_path).expanduser().resolve()
    manifest_file = (
        Path(manifest_path).expanduser().resolve()
        if manifest_path is not None
        else manifest_path_for(backup)
    )
    if not backup.is_file():
        raise BackupVerificationError("Backup file does not exist.", path=backup)
    manifest = load_backup_manifest(manifest_file)
    if manifest.backup_name != backup.name:
        raise BackupVerificationError("Backup filename does not match its manifest.", path=backup)
    if manifest.backup_size_bytes != backup.stat().st_size:
        raise BackupVerificationError("Backup size does not match its manifest.", path=backup)
    if sha256_file(backup) != manifest.sha256:
        raise BackupVerificationError("Backup SHA-256 does not match its manifest.", path=backup)
    return manifest
