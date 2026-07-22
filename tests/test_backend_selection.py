from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from persistent_memory_mcp.cli import command_init, command_status
from persistent_memory_mcp.storage import SQLiteStorage, create_sqlite_client, normalize_backend
from src.utils.db import get_supabase_client


def test_normalize_backend_aliases() -> None:
    assert normalize_backend("local") == "sqlite"
    assert normalize_backend("postgres") == "postgresql"
    assert normalize_backend(None) == "supabase"


def test_sqlite_client_supports_server_query_shape(tmp_path: Path) -> None:
    client = create_sqlite_client(tmp_path / "memory.db")
    workspace = client.table("workspaces").insert(
        {"owner_id": "owner-1", "slug": "default", "name": "Default"}
    ).execute().data[0]
    project = client.table("projects").upsert(
        {
            "owner_id": "owner-1",
            "workspace_id": workspace["id"],
            "slug": "demo",
            "name": "Demo",
            "metadata": {"source": "test"},
        }
    ).execute().data[0]
    rows = client.table("projects").select("*").eq("owner_id", "owner-1").execute().data
    assert project["id"] == rows[0]["id"]
    assert rows[0]["metadata"] == {"source": "test"}


def test_get_supabase_client_returns_sqlite_facade(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "memory.db"))
    client = get_supabase_client()
    assert client.backend_name == "sqlite"
    assert client.storage.healthcheck()[0] is True


def test_init_sqlite_creates_database_env_and_client_configs(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    output_dir = tmp_path / "configs"
    database = tmp_path / "memory.db"
    result = command_init(
        Namespace(
            env=str(env_path),
            output_dir=str(output_dir),
            clients="codex,claude",
            backend="sqlite",
            sqlite_path=str(database),
            supabase_url=None,
            supabase_key=None,
            database_url=None,
            owner_id="owner-test",
            skip_connection_test=False,
        )
    )
    assert result == 0
    assert database.exists()
    env = env_path.read_text(encoding="utf-8")
    assert "MEMORY_BACKEND=sqlite" in env
    assert f"SQLITE_PATH={database.resolve()}" in env
    assert "SUPABASE_KEY=" in env
    codex = (output_dir / "codex-config.toml").read_text(encoding="utf-8")
    assert '"MEMORY_BACKEND" = "sqlite"' in codex
    assert "SUPABASE_KEY" not in codex


def test_status_reports_local_backend_without_secrets(tmp_path: Path, capsys) -> None:
    database = tmp_path / "memory.db"
    SQLiteStorage(database).initialize()
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"MEMORY_BACKEND=sqlite\nOWNER_ID=owner-test\nSQLITE_PATH={database}\n"
        "SUPABASE_KEY=should-not-appear\n",
        encoding="utf-8",
    )
    assert command_status(Namespace(env=str(env_path))) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["backend"] == "sqlite"
    assert payload["configured"] is True
    assert "should-not-appear" not in output
