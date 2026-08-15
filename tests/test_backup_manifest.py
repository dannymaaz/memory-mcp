from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import (
    BackupDestinationError,
    BackupManifestError,
    BackupService,
    BackupVerificationError,
    load_backup_manifest,
    manifest_path_for,
    verify_backup_manifest,
)


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("pragma journal_mode = wal")
        connection.execute("create table memories (id text primary key, value text not null)")
        connection.execute(
            "insert into memories (id, value) values (?, ?)",
            ("memory-1", "secret memory content must not appear in manifest"),
        )
        connection.commit()


def test_backup_service_creates_sha256_manifest(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)

    result = BackupService(source).create_backup(target)
    manifest = verify_backup_manifest(target)

    assert result.manifest_path == manifest_path_for(target)
    assert result.manifest_path.exists()
    assert result.sha256 == manifest.sha256
    assert len(result.sha256) == 64
    assert manifest.backup_name == "backup.db"
    assert manifest.backup_size_bytes == target.stat().st_size
    assert manifest.integrity_status == "ok"
    assert manifest.table_counts == {"memories": 1}


def test_manifest_never_contains_memory_values(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)
    result = BackupService(source).create_backup(target)

    text = result.manifest_path.read_text(encoding="utf-8")
    assert "secret memory content" not in text
    assert "memory-1" not in text
    assert str(source) not in text


def test_tampered_backup_fails_sha256_verification(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)
    BackupService(source).create_backup(target)

    with target.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(BackupVerificationError, match="size does not match|SHA-256"):
        verify_backup_manifest(target)


def test_tampered_manifest_digest_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)
    result = BackupService(source).create_backup(target)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    payload["sha256"] = "0" * 64
    result.manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BackupVerificationError, match="SHA-256"):
        verify_backup_manifest(target)


def test_malformed_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.manifest.json"
    manifest.write_text("{not-json", encoding="utf-8")
    with pytest.raises(BackupManifestError, match="could not be read"):
        load_backup_manifest(manifest)


def test_unsupported_manifest_version_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)
    result = BackupService(source).create_backup(target)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    payload["format_version"] = 999
    result.manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BackupManifestError, match="Unsupported backup manifest version"):
        load_backup_manifest(result.manifest_path)


def test_existing_manifest_destination_blocks_backup(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    target = tmp_path / "backup.db"
    _database(source)
    manifest_path_for(target).write_text("{}", encoding="utf-8")

    with pytest.raises(BackupDestinationError, match="manifest destination already exists"):
        BackupService(source).create_backup(target)
    assert not target.exists()


def test_manifest_supports_unicode_paths(tmp_path: Path) -> None:
    folder = tmp_path / "copias ñ seguras"
    folder.mkdir()
    source = folder / "memoria.db"
    target = folder / "respaldo final.db"
    _database(source)

    result = BackupService(source).create_backup(target)
    manifest = verify_backup_manifest(target)
    assert result.manifest_path.exists()
    assert manifest.backup_name == "respaldo final.db"
