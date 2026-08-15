from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from persistent_memory_mcp.storage import SQLiteStorage
from persistent_memory_mcp.symbol_evolution import (
    SymbolEvolutionError,
    SymbolEvolutionScopeError,
    SymbolEvolutionService,
)

OWNER = "evolution-owner"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _database(path: Path) -> tuple[Path, str]:
    database = path / "memory.db"
    storage = SQLiteStorage(database)
    storage.initialize()
    with storage.connect() as connection:
        workspace_id = connection.execute(
            "insert into workspaces(owner_id,slug,name) values(?,?,?) returning id",
            (OWNER, "default", "Default"),
        ).fetchone()[0]
        project_id = connection.execute(
            "insert into projects(owner_id,workspace_id,slug,name) values(?,?,?,?) returning id",
            (OWNER, workspace_id, "evolution", "Evolution"),
        ).fetchone()[0]
        decision_id = connection.execute(
            "insert into decisions(project_id,owner_id,decision,rationale) values(?,?,?,?) returning id",
            (project_id, OWNER, "Keep stable symbol identity", "History must survive moves"),
        ).fetchone()[0]
        task_id = connection.execute(
            "insert into tasks(project_id,owner_id,title,details) values(?,?,?,?) returning id",
            (project_id, OWNER, "Track symbol evolution", "MEM-38"),
        ).fetchone()[0]
        connection.commit()
    return database, project_id + ":" + decision_id + ":" + task_id


def _repository(path: Path) -> tuple[Path, list[str]]:
    repo = path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "history@example.com")
    _git(repo, "config", "user.name", "History Test")

    _write(
        repo,
        "src/orders.py",
        "def process_order(order_id: str) -> str:\n"
        "    return f'order:{order_id}'\n",
    )
    _write(
        repo,
        "tests/test_orders.py",
        "from src.orders import process_order\n\n"
        "def test_process_order():\n"
        "    assert process_order('1') == 'order:1'\n",
    )
    _write(
        repo,
        "web/cart.ts",
        "export function calculateTotal(value: number) {\n"
        "  return value * 2;\n"
        "}\n",
    )
    _write(
        repo,
        "db/schema.sql",
        "CREATE TABLE sessions (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  token TEXT NOT NULL\n"
        ");\n",
    )
    commit1 = _commit(repo, "baseline symbols")

    (repo / "src/orders.py").rename(repo / "src/orders_moved.py")
    _write(
        repo,
        "tests/test_orders.py",
        "from src.orders_moved import process_order\n\n"
        "def test_process_order():\n"
        "    assert process_order('1') == 'order:1'\n",
    )
    _write(
        repo,
        "web/cart.ts",
        "export function calculateTotal(value: number) {\n"
        "  const normalized = Math.max(0, value);\n"
        "  return normalized * 3;\n"
        "}\n",
    )
    _write(
        repo,
        "db/schema.sql",
        "CREATE TABLE sessions (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  token TEXT NOT NULL,\n"
        "  created_at TEXT NOT NULL\n"
        ");\n",
    )
    commit2 = _commit(repo, "move and modify symbols")

    _write(
        repo,
        "src/orders_moved.py",
        "def finalize_order(order_id: str) -> str:\n"
        "    return f'order:{order_id}'\n",
    )
    _write(
        repo,
        "tests/test_orders.py",
        "from src.orders_moved import finalize_order\n\n"
        "def test_finalize_order():\n"
        "    assert finalize_order('1') == 'order:1'\n",
    )
    (repo / "web/cart.ts").unlink()
    commit3 = _commit(repo, "rename and delete symbols")
    return repo, [commit1, commit2, commit3]


def _checkout(repo: Path, commit: str) -> None:
    _git(repo, "checkout", "--detach", commit)


def test_symbol_history_tracks_move_modify_rename_delete_and_is_idempotent(tmp_path: Path) -> None:
    database, ids = _database(tmp_path)
    project_id, decision_id, task_id = ids.split(":")
    repo, commits = _repository(tmp_path)
    service = SymbolEvolutionService(database, owner_id=OWNER)

    _checkout(repo, commits[0])
    first = service.capture(project_id, str(repo))
    assert first["changes"]["added"] >= 4
    again = service.capture(project_id, str(repo))
    assert again["idempotent"] is True

    _checkout(repo, commits[1])
    second = service.capture(project_id, str(repo))
    assert second["changes"]["moved"] >= 1
    assert second["changes"]["modified"] >= 2
    assert second["test_links"] >= 1

    moved_history = service.history(project_id, str(repo), "process_order", token_budget=2400)
    logical_id = moved_history["logical_id"]
    assert moved_history["current_state"] == "verified"
    assert {change["change_type"] for change in moved_history["changes"]} >= {"added", "moved"}
    assert any(link["target_type"] == "test" for link in moved_history["links"])

    decision_link = service.link_memory(
        project_id,
        str(repo),
        logical_id,
        target_type="decision",
        target_id=decision_id,
        relation_type="explained_by",
    )["link"]
    task_link = service.link_memory(
        project_id,
        str(repo),
        logical_id,
        target_type="task",
        target_id=task_id,
        relation_type="implemented_by",
    )["link"]
    assert decision_link["verification_state"] == "verified"
    assert task_link["verification_state"] == "verified"

    invalidated = service.invalidate_link(
        project_id,
        decision_link["id"],
        state="contradicted",
        reason="Superseded after architecture review",
    )["link"]
    assert invalidated["verification_state"] == "contradicted"

    _checkout(repo, commits[2])
    third = service.capture(project_id, str(repo))
    assert third["changes"]["renamed"] >= 1
    assert third["changes"]["deleted"] >= 1

    renamed = service.history(project_id, str(repo), "finalize_order", token_budget=2400)
    assert renamed["logical_id"] == logical_id
    assert {change["change_type"] for change in renamed["changes"]} >= {"added", "moved", "renamed"}
    assert any(link["verification_state"] == "contradicted" for link in renamed["links"])

    deleted = service.history(project_id, str(repo), "calculateTotal", token_budget=2200)
    assert deleted["current_state"] == "missing_source"
    assert deleted["changes"][0]["change_type"] == "deleted"

    diff = service.compare_commits(project_id, str(repo), commits[1], commits[2])
    assert diff["counts"]["renamed"] >= 1
    assert diff["counts"]["deleted"] >= 1


def test_history_marks_current_snapshot_stale_after_dirty_change_and_capture_fails_closed(
    tmp_path: Path,
) -> None:
    database, ids = _database(tmp_path)
    project_id = ids.split(":")[0]
    repo, commits = _repository(tmp_path)
    service = SymbolEvolutionService(database, owner_id=OWNER)

    _checkout(repo, commits[2])
    service.capture(project_id, str(repo))
    path = repo / "src/orders_moved.py"
    path.write_text(path.read_text(encoding="utf-8") + "\n# dirty\n", encoding="utf-8")

    history = service.history(project_id, str(repo), "finalize_order")
    assert history["current_state"] == "stale"
    with pytest.raises(SymbolEvolutionError, match="clean Git working tree"):
        service.capture(project_id, str(repo))


def test_memory_links_enforce_owner_project_scope(tmp_path: Path) -> None:
    database, ids = _database(tmp_path)
    project_id = ids.split(":")[0]
    repo, commits = _repository(tmp_path)
    service = SymbolEvolutionService(database, owner_id=OWNER)
    _checkout(repo, commits[0])
    service.capture(project_id, str(repo))

    with pytest.raises(SymbolEvolutionScopeError):
        service.link_memory(
            project_id,
            str(repo),
            "process_order",
            target_type="task",
            target_id="missing-task",
        )

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "select count(*) from code_symbol_snapshot_runs where owner_id=? and project_id=?",
            (OWNER, project_id),
        ).fetchone()[0] == 1
