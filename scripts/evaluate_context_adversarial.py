"""Evaluate fail-safe Context Compiler behavior for rename, contradiction and dirty Git state."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from persistent_memory_mcp.storage import SQLiteStorage
from persistent_memory_mcp.symbol_evolution import SymbolEvolutionService

OWNER = "adversarial-owner"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(repo: Path, content: str) -> None:
    (repo / "orders.py").write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _project(database: Path) -> tuple[str, str]:
    storage = SQLiteStorage(database)
    storage.initialize()
    with storage.connect() as connection:
        workspace_id = connection.execute(
            "insert into workspaces(owner_id,slug,name) values(?,?,?) returning id",
            (OWNER, "default", "Default"),
        ).fetchone()[0]
        project_id = connection.execute(
            "insert into projects(owner_id,workspace_id,slug,name) values(?,?,?,?) returning id",
            (OWNER, workspace_id, "adversarial", "Adversarial"),
        ).fetchone()[0]
        task_id = connection.execute(
            "insert into tasks(project_id,owner_id,title,details) values(?,?,?,?) returning id",
            (project_id, OWNER, "Rename order function", "Adversarial provenance fixture"),
        ).fetchone()[0]
        connection.commit()
    return str(project_id), str(task_id)


def evaluate() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="memory-mcp-adversarial-") as temp_name:
        root = Path(temp_name)
        database = root / "memory.db"
        project_id, task_id = _project(database)
        repo = root / "repo"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "adversarial@example.com")
        _git(repo, "config", "user.name", "Adversarial Evaluation")

        service = SymbolEvolutionService(database, owner_id=OWNER)
        _write(
            repo,
            "def process_order(order_id: str) -> str:\n"
            "    return f'order:{order_id}'\n",
        )
        _commit(repo, "baseline order symbol")
        service.capture(project_id, str(repo))
        before = service.history(project_id, str(repo), "process_order", token_budget=1200)
        logical_id = str(before["logical_id"])

        _write(
            repo,
            "def finalize_order(order_id: str) -> str:\n"
            "    return f'order:{order_id}'\n",
        )
        _commit(repo, "rename order symbol")
        service.capture(project_id, str(repo))
        after = service.history(project_id, str(repo), "finalize_order", token_budget=1200)
        rename_preserved = after["logical_id"] == logical_id
        rename_classified = any(
            item.get("change_type") == "renamed" for item in after.get("changes", [])
        )

        linked = service.link_memory(
            project_id,
            str(repo),
            logical_id,
            target_type="task",
            target_id=task_id,
            relation_type="implemented_by",
        )["link"]
        contradicted = service.invalidate_link(
            project_id,
            str(linked["id"]),
            state="contradicted",
            reason="fixture contradiction",
        )
        contradicted_history = service.history(
            project_id, str(repo), logical_id, token_budget=1400
        )
        contradiction_preserved = contradicted["link"]["verification_state"] == "contradicted" and any(
            item.get("verification_state") == "contradicted"
            for item in contradicted_history.get("links", [])
        )

        path = repo / "orders.py"
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\n# dirty uncommitted change\n", encoding="utf-8")
        dirty_history = service.history(project_id, str(repo), logical_id, token_budget=1200)
        dirty_marked_stale = dirty_history["current_state"] == "stale"

        checks = {
            "rename_preserves_logical_id": rename_preserved,
            "rename_is_classified": rename_classified,
            "contradicted_evidence_is_preserved": contradiction_preserved,
            "dirty_repository_marks_current_evidence_stale": dirty_marked_stale,
        }
        return {"passed": all(checks.values()), "checks": checks}


def main() -> int:
    report = evaluate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
