from __future__ import annotations

import json
import sqlite3
from argparse import Namespace
from pathlib import Path

import pytest

from persistent_memory_mcp.migration_cli import command_migrate
from persistent_memory_mcp.migration_service import MigrationService
from persistent_memory_mcp.runtime import _assert_migration_ready
from persistent_memory_mcp.settings import RuntimeSettings
from persistent_memory_mcp.storage import SQLiteStorage


def _legacy_database(path: Path) -> None:
    storage = SQLiteStorage(path)
    storage.initialize(bootstrap_migrations=False)
    connection = sqlite3.connect(path)
    try:
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 0
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='schema_migrations'"
        ).fetchone() is None
    finally:
        connection.close()


def _env_file(path: Path, database: Path) -> Path:
    env_path = path / ".env"
    env_path.write_text(
        f"MEMORY_BACKEND=sqlite\nSQLITE_PATH={database}\nOWNER_ID=test-owner\n",
        encoding="utf-8",
    )
    return env_path


def _clear_storage_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "MEMORY_BACKEND",
        "MEMORY_STORAGE_BACKEND",
        "SQLITE_PATH",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_migration_preview_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_storage_environment(monkeypatch)
    database = tmp_path / "memory.db"
    _legacy_database(database)
    env_path = _env_file(tmp_path, database)

    result = command_migrate(
        Namespace(env=str(env_path), backup_dir=None, apply=False, yes=False)
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "preview"
    assert payload["plan"]["schema_version"] == 0
    assert payload["plan"]["pending"][0]["version"] == 1
    connection = sqlite3.connect(database)
    try:
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 0
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='schema_migrations'"
        ).fetchone() is None
    finally:
        connection.close()


def test_apply_requires_explicit_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_storage_environment(monkeypatch)
    database = tmp_path / "memory.db"
    _legacy_database(database)
    env_path = _env_file(tmp_path, database)

    result = command_migrate(
        Namespace(env=str(env_path), backup_dir=None, apply=True, yes=False)
    )

    assert result == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "confirmation_required"
    connection = sqlite3.connect(database)
    try:
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 0
    finally:
        connection.close()


def test_explicit_apply_upgrades_and_creates_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_storage_environment(monkeypatch)
    database = tmp_path / "memory.db"
    _legacy_database(database)
    env_path = _env_file(tmp_path, database)
    backup_dir = tmp_path / "verified-backups"

    result = command_migrate(
        Namespace(
            env=str(env_path),
            backup_dir=str(backup_dir),
            apply=True,
            yes=True,
        )
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["backup"]["backup_path"]
    assert Path(payload["backup"]["backup_path"]).exists()
    assert Path(payload["backup"]["manifest_path"]).exists()
    connection = sqlite3.connect(database)
    try:
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 1
        assert connection.execute(
            "select version from schema_migrations order by version"
        ).fetchall() == [(1,)]
    finally:
        connection.close()


def test_runtime_guard_blocks_existing_pending_schema(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _legacy_database(database)
    settings = RuntimeSettings(backend="sqlite", sqlite_path=database)

    with pytest.raises(RuntimeError, match="memory-mcp-migrate --apply --yes"):
        _assert_migration_ready(settings)


def test_runtime_guard_allows_current_schema(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _legacy_database(database)
    MigrationService(database).apply(tmp_path / "backups")
    settings = RuntimeSettings(backend="sqlite", sqlite_path=database)

    _assert_migration_ready(settings)


def test_runtime_guard_allows_missing_database_for_first_init(tmp_path: Path) -> None:
    settings = RuntimeSettings(backend="sqlite", sqlite_path=tmp_path / "missing.db")

    _assert_migration_ready(settings)


def test_new_sqlite_database_is_initialized_at_current_schema(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"

    SQLiteStorage(database).initialize()

    plan = MigrationService(database).plan()
    assert plan.schema_version == 1
    assert plan.pending == ()
    assert [item["version"] for item in plan.applied] == [1]
