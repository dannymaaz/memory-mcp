from __future__ import annotations

from persistent_memory_mcp.deployment_storage import install_deployment_storage
from persistent_memory_mcp.storage import SQLiteStorage


def test_deployment_storage_creates_table(tmp_path) -> None:
    install_deployment_storage()
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    project = storage.insert(
        "projects",
        {
            "owner_id": "owner-1",
            "name": "Project One",
            "slug": "project-one",
        },
    )
    row = storage.insert(
        "deployment_records",
        {
            "project_id": project["id"],
            "owner_id": "owner-1",
            "service": "api",
            "environment": "staging",
            "host": "localhost",
            "directory": "/srv/api",
            "restart_command": "systemctl restart api",
            "commit_sha": "abc",
            "result": "success",
            "tests": ["pytest"],
            "rollback_plan": {"available": True},
            "risk_reasons": ["operational terms: deploy"],
        },
    )
    assert row["project_id"] == project["id"]
    assert row["service"] == "api"
    assert row["tests"] == ["pytest"]
    assert row["rollback_plan"] == {"available": True}
