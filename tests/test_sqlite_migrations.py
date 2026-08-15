from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import (
    MigrationChecksumError,
    MigrationCompatibilityError,
    MigrationExecutionError,
    MigrationService,
    verify_backup_manifest,
)
from persistent_memory_mcp.storage import SQLiteStorage


def _v020_database(path: Path) -> tuple[str, str]:
    storage = SQLiteStorage(path)
    storage.initialize()
    with storage.connect() as connection:
        workspace_id = str(
            connection.execute(
                "insert into workspaces (owner_id, slug, name) values (?, ?, ?) returning id",
                ("owner-1", "default", "Default"),
            ).fetchone()[0]
        )
        project_id = str(
            connection.execute(
                "insert into projects (owner_id, workspace_id, slug, name) values (?, ?, ?, ?) returning id",
                ("owner-1", workspace_id, "demo", "Demo"),
            ).fetchone()[0]
        )
        connection.execute(
            "insert into tasks (project_id, owner_id, title, details) values (?, ?, ?, ?)",
            (project_id, "owner-1", "keep me", "v0.2 data"),
        )
        connection.commit()
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 0
    return workspace_id, project_id


def test_plan_is_read_only_and_reports_v020_upgrade(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    _v020_database(database)

    plan = MigrationService(database).plan()

    assert plan.current_schema_version == 0
    assert [item["version"] for item in plan.pending] == [1]
    assert plan.backup_required is True
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='schema_migrations'"
        ).fetchone() is None
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 0


def test_apply_upgrades_v020_preserves_data_and_creates_verified_backup(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backups = tmp_path / "backups"
    _v020_database(database)

    result = MigrationService(database).apply(backups)

    assert result["status"] == "ok"
    assert result["applied"][0]["version"] == 1
    backup_path = Path(str(result["backup"]["backup_path"]))
    verify_backup_manifest(backup_path)
    with sqlite3.connect(database) as connection:
        assert int(connection.execute("pragma user_version").fetchone()[0]) == 1
        row = connection.execute("select title, details from tasks").fetchone()
        assert row == ("keep me", "v0.2 data")
        migration = connection.execute(
            "select version, name, checksum from schema_migrations"
        ).fetchone()
        assert migration[0] == 1
        assert migration[1] == "v0_3_schema_baseline"
        assert len(str(migration[2])) == 64


def test_repeated_apply_is_idempotent_and_does_not_create_another_backup(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backups = tmp_path / "backups"
    _v020_database(database)
    service = MigrationService(database)
    service.apply(backups)
    before = sorted(backups.glob("*.db"))

    result = service.apply(backups)

    assert result["status"] == "current"
    assert result["applied"] == []
    assert sorted(backups.glob("*.db")) == before


def test_applied_migration_checksum_change_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backups = tmp_path / "backups"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "0001_v0_3_schema_baseline.sql"
    migration.write_text("PRAGMA user_version = 1;\n", encoding="utf-8")
    _v020_database(database)
    service = MigrationService(database, migrations)
    service.apply(backups)
    migration.write_text("PRAGMA user_version = 2;\n", encoding="utf-8")

    with pytest.raises(MigrationChecksumError, match="checksum changed"):
        service.plan()


def test_failed_migration_rolls_back_its_sql_and_is_not_recorded(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    backups = tmp_path / "backups"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_baseline.sql").write_text("PRAGMA user_version = 1;\n", encoding="utf-8")
    (migrations / "0002_broken.sql").write_text(
        "create table should_rollback (id integer);\ninsert into missing_table values (1);\n",
        encoding="utf-8",
    )
    _v020_database(database)

    with pytest.raises(MigrationExecutionError, match="0002_broken"):
        MigrationService(database, migrations).apply(backups)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "select 1 from sqlite_master where type='table' and name='should_rollback'"
        ).fetchone() is None
        applied = connection.execute("select version from schema_migrations order by version").fetchall()
        assert applied == [(1,)]
    assert len(list(backups.glob("*.db"))) == 1
    verify_backup_manifest(next(backups.glob("*.db")))


def test_incompatible_database_is_rejected_before_backup(tmp_path: Path) -> None:
    database = tmp_path / "unrelated.db"
    with sqlite3.connect(database) as connection:
        connection.execute("create table unrelated (id integer)")
        connection.commit()
    backups = tmp_path / "backups"

    with pytest.raises(MigrationCompatibilityError, match="missing required v0.2 tables"):
        MigrationService(database).apply(backups)

    assert not backups.exists()
