from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import verify_backup_manifest
from persistent_memory_mcp.migration_service import (
    MigrationChecksumError,
    MigrationCompatibilityError,
    MigrationExecutionError,
    MigrationService,
)
from persistent_memory_mcp.storage import SQLiteStorage


def _db(path: Path) -> None:
    storage = SQLiteStorage(path)
    storage.initialize(bootstrap_migrations=False)
    with storage.connect() as connection:
        workspace_id = connection.execute(
            "insert into workspaces(owner_id, slug, name) "
            "values('o', 'd', 'D') returning id"
        ).fetchone()[0]
        project_id = connection.execute(
            "insert into projects(owner_id, workspace_id, slug, name) "
            "values('o', ?, 'p', 'P') returning id",
            (workspace_id,),
        ).fetchone()[0]
        connection.execute(
            "insert into tasks(project_id, owner_id, title, details) "
            "values(?, 'o', 'keep', 'v0.2')",
            (project_id,),
        )
        connection.commit()


def test_plan_is_read_only(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)

    plan = MigrationService(database).plan()

    assert plan.schema_version == 0
    assert [item["version"] for item in plan.pending] == [1, 2]
    assert plan.as_dict()["backup_required"] is True
    with sqlite3.connect(database) as connection:
        tracking_table = connection.execute(
            "select 1 from sqlite_master where name='schema_migrations'"
        ).fetchone()
        assert tracking_table is None
        assert connection.execute("pragma user_version").fetchone()[0] == 0


def test_apply_preserves_data_and_creates_verified_backup(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)

    result = MigrationService(database).apply(tmp_path / "backups")

    verify_backup_manifest(Path(str(result["backup"]["backup_path"])))
    with sqlite3.connect(database) as connection:
        assert connection.execute("pragma user_version").fetchone()[0] == 2
        assert connection.execute("select title, details from tasks").fetchone() == (
            "keep",
            "v0.2",
        )
        assert connection.execute(
            "select version from schema_migrations order by version"
        ).fetchall() == [(1,), (2,)]
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table' and name like 'code_symbol_%'"
            ).fetchall()
        }
        assert tables == {
            "code_symbol_snapshot_runs",
            "code_symbol_snapshots",
            "code_symbol_changes",
            "code_symbol_links",
        }


def test_idempotent_apply_creates_no_second_backup(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    service = MigrationService(database)
    service.apply(tmp_path / "b")
    before = list((tmp_path / "b").glob("*.db"))

    result = service.apply(tmp_path / "b")

    assert result["status"] == "current"
    assert list((tmp_path / "b").glob("*.db")) == before


def test_checksum_change_rejected(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    migrations = (
        {"version": 1, "name": "x", "sql": "PRAGMA user_version=1;"},
    )
    MigrationService(database, migrations).apply(tmp_path / "b")

    changed = (
        {"version": 1, "name": "x", "sql": "PRAGMA user_version=2;"},
    )
    with pytest.raises(MigrationChecksumError):
        MigrationService(database, changed).plan()


def test_failed_migration_rolls_back_its_transaction(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    migrations = (
        {"version": 1, "name": "ok", "sql": "PRAGMA user_version=1;"},
        {
            "version": 2,
            "name": "bad",
            "sql": (
                "create table rollback_me(id integer); "
                "insert into missing_table values(1);"
            ),
        },
    )

    with pytest.raises(MigrationExecutionError):
        MigrationService(database, migrations).apply(tmp_path / "b")

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "select 1 from sqlite_master where name='rollback_me'"
        ).fetchone() is None
        assert connection.execute(
            "select version from schema_migrations order by version"
        ).fetchall() == [(1,)]
        assert connection.execute("pragma user_version").fetchone()[0] == 1


def test_incompatible_database_rejected_before_backup(tmp_path: Path) -> None:
    database = tmp_path / "x.db"
    with sqlite3.connect(database) as connection:
        connection.execute("create table x(id)")
        connection.commit()

    with pytest.raises(MigrationCompatibilityError):
        MigrationService(database).apply(tmp_path / "b")

    assert not (tmp_path / "b").exists()


def test_future_schema_version_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    with sqlite3.connect(database) as connection:
        connection.execute("pragma user_version = 99")
        connection.commit()

    with pytest.raises(MigrationCompatibilityError, match="newer than supported"):
        MigrationService(database).plan()


def test_missing_history_for_claimed_schema_version_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    with sqlite3.connect(database) as connection:
        connection.execute("pragma user_version = 1")
        connection.commit()

    with pytest.raises(MigrationCompatibilityError, match="history is missing"):
        MigrationService(database).plan()


def test_duplicate_migration_versions_are_rejected(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    duplicates = (
        {"version": 1, "name": "one", "sql": "PRAGMA user_version=1;"},
        {"version": 1, "name": "two", "sql": "PRAGMA user_version=1;"},
    )

    with pytest.raises(MigrationCompatibilityError, match="duplicate migration version"):
        MigrationService(database, duplicates)


def test_migration_cannot_manage_its_own_transaction(tmp_path: Path) -> None:
    database = tmp_path / "m.db"
    _db(database)
    unsafe = (
        {
            "version": 1,
            "name": "unsafe",
            "sql": "BEGIN; PRAGMA user_version=1; COMMIT;",
        },
    )

    with pytest.raises(MigrationCompatibilityError, match="must not manage transactions"):
        MigrationService(database, unsafe)


def test_fresh_database_bootstrap_marks_packaged_schema_current(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    SQLiteStorage(database).initialize(bootstrap_migrations=False)

    plan = MigrationService(database).bootstrap_fresh_database()

    assert plan.schema_version == 2
    assert plan.pending == ()
    assert [item["version"] for item in plan.applied] == [1, 2]
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table' and name like 'code_symbol_%'"
            ).fetchall()
        }
    assert "code_symbol_snapshots" in tables
    assert "code_symbol_changes" in tables


def test_fresh_database_bootstrap_refuses_existing_user_data(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    _db(database)

    with pytest.raises(MigrationCompatibilityError, match="data already exists"):
        MigrationService(database).bootstrap_fresh_database()
