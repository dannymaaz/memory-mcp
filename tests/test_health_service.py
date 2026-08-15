from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import BackupService, HealthError, HealthService
from persistent_memory_mcp.storage import SQLiteStorage


def _initialized_database(path: Path) -> None:
    storage = SQLiteStorage(path)
    storage.initialize()
    with storage.connect() as connection:
        workspace_id = connection.execute(
            "insert into workspaces (owner_id, slug, name) values (?, ?, ?) returning id",
            ("owner-1", "default", "Default"),
        ).fetchone()[0]
        connection.execute(
            "insert into projects (owner_id, workspace_id, slug, name) values (?, ?, ?, ?)",
            ("owner-1", workspace_id, "demo", "Demo"),
        )
        connection.commit()


def test_healthy_initialized_database_reports_structural_state(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _initialized_database(database)

    result = HealthService(database).check()

    assert result.status == "healthy"
    assert result.database_name == "memory.db"
    assert result.quick_check == ("ok",)
    assert result.integrity_check is None
    assert result.foreign_key_violations == ()
    assert result.missing_indexes == ()
    assert result.database_size_bytes > 0
    assert result.disk_free_bytes > 0
    assert result.latest_verified_backup is None
    assert result.maintenance_ready is False


def test_full_integrity_check_is_available_explicitly(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _initialized_database(database)

    result = HealthService(database).check(full_integrity=True)

    assert result.status == "healthy"
    assert result.integrity_check == ("ok",)


def test_missing_expected_index_degrades_health(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _initialized_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("drop index idx_tasks_scope")
        connection.commit()

    result = HealthService(database).check()

    assert result.status == "degraded"
    assert result.missing_indexes == ("idx_tasks_scope",)
    assert result.maintenance_ready is False


def test_foreign_key_violation_is_reported_without_memory_values(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _initialized_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("pragma foreign_keys = off")
        connection.execute(
            "insert into tasks (project_id, owner_id, title, details) values (?, ?, ?, ?)",
            ("missing-project", "owner-1", "orphan", "sensitive task details"),
        )
        connection.commit()

    result = HealthService(database).check()
    payload = result.as_dict()

    assert result.status == "degraded"
    assert len(result.foreign_key_violations) == 1
    violation = result.foreign_key_violations[0]
    assert violation["table"] == "tasks"
    assert violation["parent"] == "projects"
    assert "sensitive task details" not in str(payload)


def test_latest_verified_backup_is_reported_from_configured_directory(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backup_dir = tmp_path / "backups"
    _initialized_database(database)
    backup = BackupService(database).create_backup(backup_dir / "backup.db")

    result = HealthService(database, backup_directory=backup_dir).check()

    assert result.status == "healthy"
    assert result.maintenance_ready is True
    assert result.latest_verified_backup is not None
    assert result.latest_verified_backup["backup_name"] == "backup.db"
    assert result.latest_verified_backup["sha256"] == backup.sha256
    assert result.invalid_backup_manifests == 0


def test_invalid_manifest_is_counted_but_not_exposed(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _initialized_database(database)
    (backup_dir / "broken.manifest.json").write_text("{broken", encoding="utf-8")

    result = HealthService(database, backup_directory=backup_dir).check()

    assert result.status == "healthy"
    assert result.invalid_backup_manifests == 1
    assert result.latest_verified_backup is None


def test_missing_database_returns_typed_error(tmp_path: Path) -> None:
    with pytest.raises(HealthError, match="does not exist") as exc_info:
        HealthService(tmp_path / "missing.db").check()

    assert exc_info.value.code == "health_error"
