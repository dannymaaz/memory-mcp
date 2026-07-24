from __future__ import annotations

import pytest

from persistent_memory_mcp.dashboard import DashboardConfig, dashboard_snapshot, render_dashboard
from persistent_memory_mcp.storage import SQLiteStorage


def test_dashboard_rejects_remote_binding(tmp_path) -> None:
    config = DashboardConfig(host="0.0.0.0", sqlite_path=tmp_path / "memory.db")
    with pytest.raises(ValueError, match="localhost"):
        config.validate()


def test_dashboard_snapshot_is_bounded(tmp_path) -> None:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    workspace = storage.insert("workspaces", {"owner_id": "owner-1", "name": "Local", "slug": "local"})
    project = storage.insert(
        "projects",
        {"workspace_id": workspace["id"], "owner_id": "owner-1", "name": "Project", "slug": "project"},
    )
    storage.insert(
        "tasks",
        {"project_id": project["id"], "owner_id": "owner-1", "title": "One", "status": "pending"},
    )
    storage.insert(
        "tasks",
        {"project_id": project["id"], "owner_id": "owner-1", "title": "Two", "status": "pending"},
    )
    snapshot = dashboard_snapshot(storage, limit=1)
    assert snapshot["read_only"] is True
    assert snapshot["counts"]["tasks"] == 2
    assert len(snapshot["tables"]["tasks"]) == 1


def test_dashboard_html_escapes_stored_content() -> None:
    rendered = render_dashboard(
        {
            "counts": {"tasks": 1},
            "tables": {"tasks": [{"title": "<script>alert(1)</script>"}]},
        }
    )
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
