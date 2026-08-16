from __future__ import annotations

from pathlib import Path

import pytest

from persistent_memory_mcp.dashboard_status import (
    DashboardStatusError,
    DashboardStatusService,
)
from persistent_memory_mcp.maintenance import BackupService
from persistent_memory_mcp.storage import SQLiteStorage


STAMP = "2026-08-16T05:00:00+00:00"


def _storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Dashboard status",
            "slug": "dashboard-status",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return storage


def _seed_status_data(storage: SQLiteStorage) -> None:
    storage.insert(
        "tasks",
        {
            "id": "task-1",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Sensitive task",
            "status": "pending",
            "sensitivity": "restricted",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "decisions",
        {
            "id": "decision-1",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "summary": "Keep local",
            "details": "Dashboard maintenance",
            "sensitivity": "internal",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    with storage.connect() as connection:
        connection.execute(
            "insert into code_symbol_links("
            "id, project_id, owner_id, repository, logical_id, relation_type, target_type, "
            "target_id, verification_state, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "link-1",
                "project-1",
                "owner-1",
                "github.com/example/repo",
                "symbol-1",
                "implemented_by",
                "task",
                "task-1",
                "stale",
                STAMP,
                STAMP,
            ),
        )
        connection.commit()


def test_status_composes_health_storage_verification_and_sensitivity(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    _seed_status_data(storage)

    result = DashboardStatusService(storage, owner_id="owner-1").read(
        project_id="project-1"
    )

    assert result["status"] == "healthy"
    assert result["read_only"] is True
    assert result["health"]["maintenance_ready"] is False
    assert result["health"]["quick_check"] == ["ok"]
    assert result["storage"]["database_size_bytes"] > 0
    assert result["storage"]["disk_free_bytes"] > 0
    assert result["backup"] == {
        "configured": False,
        "latest_verified": None,
        "invalid_manifests": 0,
    }
    assert result["verification"]["evidence_states"]["stale"] == 1
    assert result["verification"]["evidence_risk_count"] == 1
    assert result["sensitivity"]["totals"] == {"internal": 1, "restricted": 1}
    serialized = str(result)
    assert str(storage.path) not in serialized
    assert str(tmp_path) not in serialized


def test_status_detects_latest_verified_backup_without_exposing_paths(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup = BackupService(storage.path).create_backup(backup_dir / "verified.db")

    result = DashboardStatusService(
        storage,
        owner_id="owner-1",
        backup_directory=backup_dir,
    ).read(project_id="project-1")

    assert result["backup"]["configured"] is True
    latest = result["backup"]["latest_verified"]
    assert latest is not None
    assert latest["backup_name"] == "verified.db"
    assert latest["sha256"] == backup.sha256
    assert result["health"]["maintenance_ready"] is True
    serialized = str(result)
    assert str(backup_dir) not in serialized
    assert str(backup.backup_path) not in serialized


def test_status_is_owner_scoped(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    storage.insert(
        "projects",
        {
            "id": "project-2",
            "owner_id": "owner-2",
            "name": "Foreign",
            "slug": "foreign",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "tasks",
        {
            "id": "foreign-task",
            "project_id": "project-2",
            "owner_id": "owner-2",
            "title": "Foreign restricted",
            "status": "pending",
            "sensitivity": "secret",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )

    result = DashboardStatusService(storage, owner_id="owner-1").read(
        project_id="project-1"
    )
    assert "secret" not in result["sensitivity"]["totals"]
    with pytest.raises(DashboardStatusError, match="owner scope"):
        DashboardStatusService(storage, owner_id="owner-1").read(project_id="project-2")


def test_status_fails_closed_when_owner_is_ambiguous(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    storage.insert(
        "projects",
        {
            "id": "project-2",
            "owner_id": "owner-2",
            "name": "Foreign",
            "slug": "foreign",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    with pytest.raises(DashboardStatusError, match="multiple owners"):
        DashboardStatusService(storage)
