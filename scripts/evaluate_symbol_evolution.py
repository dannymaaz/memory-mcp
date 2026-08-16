"""Report deterministic symbol-evolution metrics across a small multi-language Git history."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from persistent_memory_mcp.storage import SQLiteStorage
from persistent_memory_mcp.symbol_evolution import SymbolEvolutionService

OWNER = "symbol-eval-owner"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _project(database: Path) -> str:
    storage = SQLiteStorage(database)
    storage.initialize()
    with storage.connect() as connection:
        workspace_id = connection.execute(
            "insert into workspaces(owner_id,slug,name) values(?,?,?) returning id",
            (OWNER, "default", "Default"),
        ).fetchone()[0]
        project_id = connection.execute(
            "insert into projects(owner_id,workspace_id,slug,name) values(?,?,?,?) returning id",
            (OWNER, workspace_id, "symbol-eval", "Symbol Evaluation"),
        ).fetchone()[0]
        connection.commit()
    return str(project_id)


def _baseline(repo: Path) -> str:
    _write(
        repo,
        "src/orders.py",
        "def process_order(order_id: str) -> str:\n"
        "    return f'order:{order_id}'\n",
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
        "web/status.js",
        "export function statusLabel(active) {\n"
        "  return active ? 'on' : 'off';\n"
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
    return _commit(repo, "symbol evaluation baseline")


def _evolve(repo: Path) -> str:
    _write(
        repo,
        "src/orders.py",
        "def finalize_order(order_id: str) -> str:\n"
        "    return f'order:{order_id}'\n",
    )
    (repo / "web/cart.ts").rename(repo / "web/pricing.ts")
    _write(
        repo,
        "web/status.js",
        "export function statusLabel(active) {\n"
        "  const normalized = Boolean(active);\n"
        "  return normalized ? 'active' : 'inactive';\n"
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
    return _commit(repo, "rename move and modify symbols")


def evaluate() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="memory-mcp-symbol-eval-") as temp_name:
        root = Path(temp_name)
        repo = root / "repo"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "symbol-eval@example.com")
        _git(repo, "config", "user.name", "Symbol Evaluation")

        database = root / "memory.db"
        project_id = _project(database)
        service = SymbolEvolutionService(database, owner_id=OWNER)

        first_commit = _baseline(repo)
        first_capture = service.capture(project_id, str(repo))
        old_history = service.history(project_id, str(repo), "process_order", token_budget=1600)
        logical_id = old_history["logical_id"]

        second_commit = _evolve(repo)
        second_capture = service.capture(project_id, str(repo))
        new_history = service.history(project_id, str(repo), "finalize_order", token_budget=1600)
        diff = service.compare_commits(project_id, str(repo), first_commit, second_commit)

        languages = set()
        for symbol in new_history.get("snapshots", []):
            language = symbol.get("language")
            if language:
                languages.add(str(language))

        connection = sqlite3.connect(database)
        try:
            languages.update(
                str(row[0])
                for row in connection.execute(
                    "select distinct language from code_symbol_snapshots "
                    "where owner_id=? and project_id=? and repository=?",
                    (OWNER, project_id, str(repo.resolve())),
                ).fetchall()
                if row[0]
            )
        finally:
            connection.close()

        counts = diff["counts"]
        checks = {
            "initial_symbols_captured": int(first_capture.get("symbol_count", 0)) >= 4,
            "rename_preserves_logical_id": new_history["logical_id"] == logical_id,
            "renamed_classified": int(counts.get("renamed", 0)) >= 1,
            "moved_classified": int(counts.get("moved", 0)) >= 1,
            "modified_classified": int(counts.get("modified", 0)) >= 1,
            "current_state_verified": new_history["current_state"] == "verified",
            "python_covered": "python" in languages,
            "typescript_covered": "typescript" in languages,
            "javascript_covered": "javascript" in languages,
            "sql_covered": "sql" in languages,
        }
        passed = all(checks.values())
        return {
            "passed": passed,
            "commits": [first_commit, second_commit],
            "first_capture": {
                "symbol_count": first_capture.get("symbol_count", 0),
                "changes": first_capture.get("changes", {}),
            },
            "second_capture": {
                "symbol_count": second_capture.get("symbol_count", 0),
                "changes": second_capture.get("changes", {}),
            },
            "classified_changes": counts,
            "languages": sorted(languages),
            "checks": checks,
        }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
