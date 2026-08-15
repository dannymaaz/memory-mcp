from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import (
    BackupDestinationError,
    BackupError,
    BackupService,
)
from persistent_memory_mcp.storage import SQLiteStorage


def _wal_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    mode = connection.execute("pragma journal_mode = wal").fetchone()[0]
    assert mode == "wal"
    connection.execute("create table memories (id text primary key, value text not null)")
    connection.execute("insert into memories (id, value) values (?, ?)", ("memory-1", "keep me"))
    connection.commit()
    return connection


def test_backup_succeeds_while_wal_database_is_open(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    try:
        result = BackupService(source).create_backup(tmp_path / "backup.db")
    finally:
        writer.close()

    assert result.integrity_status == "ok"
    assert result.table_counts == {"memories": 1}
    assert result.source_size_bytes > 0
    assert result.backup_size_bytes > 0
    assert result.sqlite_version

    with sqlite3.connect(result.backup_path) as connection:
        assert connection.execute("select value from memories where id = 'memory-1'").fetchone()[0] == "keep me"
        assert connection.execute("pragma integrity_check").fetchone()[0] == "ok"


def test_backup_preserves_source_records(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    try:
        before = writer.execute("select id, value from memories order by id").fetchall()
        BackupService(source).create_backup(tmp_path / "backup.db")
        after = writer.execute("select id, value from memories order by id").fetchall()
    finally:
        writer.close()

    assert after == before


def test_existing_destination_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    target = tmp_path / "backup.db"
    target.write_bytes(b"existing")
    try:
        with pytest.raises(BackupDestinationError, match="already exists"):
            BackupService(source).create_backup(target)
    finally:
        writer.close()
    assert target.read_bytes() == b"existing"


def test_source_and_destination_must_differ(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    try:
        with pytest.raises(BackupDestinationError, match="must differ"):
            BackupService(source).create_backup(source)
    finally:
        writer.close()


def test_temporary_file_is_cleaned_after_backup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    service = BackupService(source)

    def fail_copy(_source: Path, temporary: Path) -> None:
        temporary.write_bytes(b"incomplete")
        raise sqlite3.OperationalError("injected failure")

    monkeypatch.setattr(service, "_copy_database", fail_copy)
    try:
        with pytest.raises(BackupError, match="backup creation failed"):
            service.create_backup(tmp_path / "backup.db")
    finally:
        writer.close()

    assert not (tmp_path / "backup.db").exists()
    assert not list(tmp_path.glob(".backup.db.*.tmp"))


def test_missing_parent_directory_is_created(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    target = tmp_path / "nested" / "backups" / "backup.db"
    try:
        result = BackupService(source).create_backup(target)
    finally:
        writer.close()
    assert result.backup_path == target.resolve()
    assert target.exists()


def test_invalid_destination_returns_structured_error(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    writer = _wal_database(source)
    invalid_parent = tmp_path / "not-a-directory"
    invalid_parent.write_text("file", encoding="utf-8")
    try:
        with pytest.raises(BackupDestinationError) as exc_info:
            BackupService(source).create_backup(invalid_parent / "backup.db")
    finally:
        writer.close()

    details = exc_info.value.as_dict()
    assert details["code"] == "backup_destination_error"
    assert "message" in details


def test_empty_initialized_database_can_be_backed_up(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    SQLiteStorage(source).initialize()
    result = BackupService(source).create_backup(tmp_path / "backup.db")
    assert result.integrity_status == "ok"
    assert "projects" in result.table_counts
    assert result.table_counts["projects"] == 0


def test_backup_supports_spaces_and_unicode_paths(tmp_path: Path) -> None:
    folder = tmp_path / "memoria local ñ"
    folder.mkdir()
    source = folder / "memoria activa.db"
    writer = _wal_database(source)
    target = folder / "copias seguras" / "respaldo verificado.db"
    try:
        result = BackupService(source).create_backup(target)
    finally:
        writer.close()
    assert result.backup_path == target.resolve()
    assert target.exists()
