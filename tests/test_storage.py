from __future__ import annotations

from pathlib import Path

import pytest

from persistent_memory_mcp.storage import SQLiteStorage, StorageAdapter, create_storage


NOW = "2026-07-22T18:00:00+00:00"


def _project() -> dict[str, object]:
    return {
        "id": "project-1",
        "owner_id": "owner-1",
        "workspace_id": None,
        "name": "Memory MCP",
        "slug": "memory-mcp",
        "description": "",
        "repo_path": "",
        "repo_remote": "",
        "repo_status": {},
        "project_summary": "",
        "metadata": {"local": True},
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_factory_creates_protocol_compatible_sqlite(tmp_path: Path) -> None:
    storage = create_storage("sqlite", sqlite_path=tmp_path / "memory.db")
    assert isinstance(storage, StorageAdapter)
    assert storage.backend_name == "sqlite"


def test_initialize_and_healthcheck(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    ok, detail = storage.healthcheck()
    assert ok is True
    assert "SQLite" in detail


def test_insert_select_and_json_round_trip(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    inserted = storage.insert("projects", _project())
    assert inserted["metadata"] == {"local": True}
    selected = storage.select("projects", {"owner_id": "owner-1", "slug": "memory-mcp"})
    assert selected[0]["id"] == "project-1"
    assert selected[0]["repo_status"] == {}


def test_upsert_updates_existing_record(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert("projects", _project())
    updated = {**_project(), "project_summary": "Local-first memory"}
    row = storage.upsert("projects", updated, conflict_columns=["id"])
    assert row["project_summary"] == "Local-first memory"


def test_delete_requires_owner_and_project_scope(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    with pytest.raises(ValueError, match="owner_id and project_id"):
        storage.delete("tasks", {"id": "task-1"})


def test_scoped_delete_only_removes_matching_owner_project(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert("projects", _project())
    task = {
        "id": "task-1",
        "project_id": "project-1",
        "owner_id": "owner-1",
        "title": "Create SQLite adapter",
        "status": "pending",
        "priority": "high",
        "details": "",
        "sensitivity": "internal",
        "expires_at": None,
        "metadata": {},
        "created_at": NOW,
        "updated_at": NOW,
    }
    storage.insert("tasks", task)
    deleted = storage.delete("tasks", {"owner_id": "owner-1", "project_id": "project-1"})
    assert deleted == 1
    assert storage.select("tasks", {"project_id": "project-1"}) == []


def test_unknown_table_is_rejected(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    with pytest.raises(ValueError, match="Unsupported storage table"):
        storage.select("users")


def test_unknown_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="MEMORY_BACKEND"):
        create_storage("unknown")
