from __future__ import annotations

import sqlite3

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


def test_deployment_wrapper_preserves_initialize_keyword_options(tmp_path) -> None:
    install_deployment_storage()
    database = tmp_path / "legacy.db"
    storage = SQLiteStorage(database)

    storage.initialize(bootstrap_migrations=False)

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("pragma user_version").fetchone()[0] == 0
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='deployment_records'"
        ).fetchone() == (1,)
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='schema_migrations'"
        ).fetchone() is None
    finally:
        connection.close()
