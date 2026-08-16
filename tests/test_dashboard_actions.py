from __future__ import annotations

from pathlib import Path

import pytest

from persistent_memory_mcp.dashboard_actions import (
    DashboardActionError,
    DashboardMaintenanceActions,
    _RESTORE_PLANS,
)
from persistent_memory_mcp.deletion_integration import _USED_PLAN_FINGERPRINTS
from persistent_memory_mcp.maintenance import BackupService
from persistent_memory_mcp.storage import SQLiteStorage


STAMP = "2026-08-16T05:20:00+00:00"


def _storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Maintenance actions",
            "slug": "maintenance-actions",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return storage


def _action_service(tmp_path: Path, storage: SQLiteStorage) -> DashboardMaintenanceActions:
    backup_dir = tmp_path / "backups"
    return DashboardMaintenanceActions(
        storage,
        owner_id="owner-1",
        backup_directory=backup_dir,
    )


def test_create_backup_uses_server_generated_name_and_returns_no_paths(
    tmp_path: Path,
) -> None:
    storage = _storage(tmp_path)
    service = _action_service(tmp_path, storage)
    result = service.create_backup()

    assert result["status"] == "ok"
    assert result["backup_name"].startswith("dashboard-")
    assert result["backup_name"].endswith(".db")
    assert result["manifest_name"].endswith(".manifest.json")
    assert result["integrity_status"] == "ok"
    backup_path = tmp_path / "backups" / result["backup_name"]
    assert backup_path.is_file()
    assert (tmp_path / "backups" / result["manifest_name"]).is_file()
    assert str(tmp_path) not in str(result)


def test_backup_requires_explicit_configured_directory(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    service = DashboardMaintenanceActions(storage, owner_id="owner-1", backup_directory=None)
    with pytest.raises(DashboardActionError, match="not configured"):
        service.create_backup()


def test_restore_plan_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-test-secret")
    storage = _storage(tmp_path)
    service = _action_service(tmp_path, storage)
    with pytest.raises(DashboardActionError, match="file name"):
        service.plan_restore(backup_name="../outside.db")


def test_restore_preview_and_execute_restores_verified_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-test-secret")
    _RESTORE_PLANS.clear()
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup = BackupService(storage.path).create_backup(backup_dir / "before.db")
    storage.insert(
        "tasks",
        {
            "id": "task-after-backup",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Should disappear after restore",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    service = DashboardMaintenanceActions(
        storage,
        owner_id="owner-1",
        backup_directory=backup_dir,
    )

    preview = service.plan_restore(backup_name="before.db")
    assert preview["status"] == "preview"
    assert preview["backup_name"] == "before.db"
    assert preview["backup_sha256"] == backup.sha256
    assert str(tmp_path) not in str(preview)
    assert storage.select("tasks", {"id": "task-after-backup"})

    result = service.execute_restore(
        plan_id=preview["plan_id"],
        confirmation_token=preview["confirmation_token"],
    )
    assert result["status"] == "ok"
    assert result["safety_backup_name"].endswith(".db")
    assert result["safety_manifest_name"].endswith(".manifest.json")
    assert str(tmp_path) not in str(result)
    assert storage.select("tasks", {"id": "task-after-backup"}) == []

    with pytest.raises(DashboardActionError, match="no longer available"):
        service.execute_restore(
            plan_id=preview["plan_id"],
            confirmation_token=preview["confirmation_token"],
        )


def test_deletion_preview_is_scoped_and_execution_is_single_use_across_interfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-test-secret")
    _USED_PLAN_FINGERPRINTS.clear()
    storage = _storage(tmp_path)
    storage.insert(
        "tasks",
        {
            "id": "task-delete",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Delete me",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "tasks",
        {
            "id": "task-keep",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Keep me",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    service = _action_service(tmp_path, storage)

    preview = service.plan_deletion(
        memory_type="tasks",
        project_id="project-1",
        record_ids=["task-delete", "missing"],
    )
    assert preview["status"] == "preview"
    assert preview["candidate_count"] == 1
    assert preview["missing_record_ids"] == ["missing"]
    assert storage.select("tasks", {"id": "task-delete"})

    result = service.execute_deletion(
        plan=preview["plan"],
        confirmation_token=preview["confirmation_token"],
    )
    assert result["status"] == "ok"
    assert result["deleted_count"] == 1
    assert storage.select("tasks", {"id": "task-delete"}) == []
    assert storage.select("tasks", {"id": "task-keep"})
    assert preview["plan"]["fingerprint"] in _USED_PLAN_FINGERPRINTS

    with pytest.raises(Exception, match="already been used"):
        service.execute_deletion(
            plan=preview["plan"],
            confirmation_token=preview["confirmation_token"],
        )


def test_deletion_rejects_foreign_project_and_large_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-test-secret")
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
    service = _action_service(tmp_path, storage)
    with pytest.raises(DashboardActionError, match="owner scope"):
        service.plan_deletion(
            memory_type="tasks",
            project_id="project-2",
            record_ids=["anything"],
        )
    with pytest.raises(DashboardActionError, match="at most 100"):
        service.plan_deletion(
            memory_type="tasks",
            project_id="project-1",
            record_ids=[f"task-{index}" for index in range(101)],
        )
