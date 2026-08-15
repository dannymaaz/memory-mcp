from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from persistent_memory_mcp.maintenance import (
    BackupService,
    RestoreConfirmationError,
    RestoreExecutionError,
    RestorePlanError,
    RestoreService,
    validate_restore_confirmation,
    verify_backup_manifest,
)


@pytest.fixture(autouse=True)
def restore_confirmation_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "restore-test-secret")


def _database(path: Path, value: str, *, schema_version: int = 7) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("pragma journal_mode = wal")
        connection.execute(f"pragma user_version = {schema_version}")
        connection.execute("create table state (id integer primary key, value text not null)")
        connection.execute("insert into state (id, value) values (1, ?)", (value,))
        connection.commit()


def _read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return str(connection.execute("select value from state where id = 1").fetchone()[0])


def _set_value(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("update state set value = ? where id = 1", (value,))
        connection.commit()


def _prepared_restore(tmp_path: Path) -> tuple[Path, Path, RestoreService]:
    target = tmp_path / "memory.db"
    backup = tmp_path / "restore-source.db"
    _database(target, "original-backup-state")
    BackupService(target).create_backup(backup)
    _set_value(target, "current-pre-restore-state")
    return target, backup, RestoreService(target)


def test_restore_preview_is_non_mutating_and_execution_restores_verified_backup(
    tmp_path: Path,
) -> None:
    target, backup, service = _prepared_restore(tmp_path)

    plan, token = service.plan_restore(backup)

    assert _read_value(target) == "current-pre-restore-state"
    assert plan.backup_sha256 == verify_backup_manifest(backup).sha256
    assert plan.target_path == str(target.resolve())
    assert plan.safety_backup_path != plan.target_path

    result = service.execute_restore(plan, token)

    assert result["status"] == "ok"
    assert _read_value(target) == "original-backup-state"
    safety_backup = Path(str(result["safety_backup_path"]))
    assert safety_backup.exists()
    verify_backup_manifest(safety_backup)
    assert _read_value(safety_backup) == "current-pre-restore-state"


def test_restore_confirmation_is_single_use(tmp_path: Path) -> None:
    _target, backup, service = _prepared_restore(tmp_path)
    plan, token = service.plan_restore(backup)
    service.execute_restore(plan, token)

    with pytest.raises(RestoreConfirmationError, match="already been used"):
        service.execute_restore(plan, token)


def test_tampered_backup_after_preview_is_rejected_without_touching_active_database(
    tmp_path: Path,
) -> None:
    target, backup, service = _prepared_restore(tmp_path)
    plan, token = service.plan_restore(backup)

    with backup.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(Exception, match="manifest|size|SHA-256|changed"):
        service.execute_restore(plan, token)

    assert _read_value(target) == "current-pre-restore-state"
    assert not Path(plan.safety_backup_path).exists()


def test_active_database_change_after_preview_is_rejected(tmp_path: Path) -> None:
    target, backup, service = _prepared_restore(tmp_path)
    plan, token = service.plan_restore(backup)
    _set_value(target, "changed-after-preview")

    with pytest.raises(RestorePlanError, match="active database changed"):
        service.execute_restore(plan, token)

    assert _read_value(target) == "changed-after-preview"
    assert not Path(plan.safety_backup_path).exists()


def test_schema_mismatch_is_rejected_during_preview(tmp_path: Path) -> None:
    target = tmp_path / "memory.db"
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _database(target, "current", schema_version=1)
    _database(source, "candidate", schema_version=2)
    BackupService(source).create_backup(backup)

    with pytest.raises(RestorePlanError, match="schema version is incompatible"):
        RestoreService(target).plan_restore(backup)

    assert _read_value(target) == "current"


def test_insufficient_disk_space_blocks_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, backup, service = _prepared_restore(tmp_path)
    monkeypatch.setattr(service, "_disk_free", lambda _path: 0)

    with pytest.raises(RestorePlanError, match="insufficient disk space"):
        service.plan_restore(backup)

    assert _read_value(target) == "current-pre-restore-state"


def test_expired_confirmation_is_rejected(tmp_path: Path) -> None:
    _target, backup, service = _prepared_restore(tmp_path)
    created = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    plan, token = service.plan_restore(backup, confirmation_ttl_seconds=30, now=created)

    with pytest.raises(RestoreConfirmationError, match="expired"):
        validate_restore_confirmation(plan, token, now=created + timedelta(seconds=31))


def test_modified_plan_does_not_validate_original_token(tmp_path: Path) -> None:
    _target, backup, service = _prepared_restore(tmp_path)
    plan, token = service.plan_restore(backup)
    changed = replace(plan, required_free_bytes=plan.required_free_bytes + 1)

    with pytest.raises(RestoreConfirmationError, match="plan has changed"):
        validate_restore_confirmation(changed, token)


def test_post_replace_failure_automatically_rolls_back_to_pre_restore_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, backup, service = _prepared_restore(tmp_path)
    plan, token = service.plan_restore(backup)

    def fail_validation(_target: Path, _plan: object) -> None:
        raise RestoreExecutionError("injected post-replace validation failure")

    monkeypatch.setattr(service, "_validate_restored_target", fail_validation)

    with pytest.raises(RestoreExecutionError, match="injected"):
        service.execute_restore(plan, token)

    assert _read_value(target) == "current-pre-restore-state"
    safety_backup = Path(plan.safety_backup_path)
    assert safety_backup.exists()
    verify_backup_manifest(safety_backup)
    assert _read_value(safety_backup) == "current-pre-restore-state"


def test_restore_source_cannot_be_the_active_database(tmp_path: Path) -> None:
    target = tmp_path / "memory.db"
    _database(target, "current")

    with pytest.raises(RestorePlanError, match="must differ"):
        RestoreService(target).plan_restore(target)
