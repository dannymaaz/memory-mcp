from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from persistent_memory_mcp.git_verification import (
    build_verified_search_tool,
    prefer_repository_state,
    repository_snapshot,
    verify_memory,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Memory MCP Tests")
    (repo / "app.py").write_text("print('one')\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_repository_snapshot_reads_authoritative_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    snapshot = repository_snapshot(repo)
    assert snapshot.branch == "main"
    assert snapshot.commit_sha == _git(repo, "rev-parse", "HEAD")
    assert snapshot.dirty is False


def test_verify_memory_marks_matching_evidence_verified(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    commit = _git(repo, "rev-parse", "HEAD")
    digest = hashlib.sha256((repo / "app.py").read_bytes()).hexdigest()
    result = verify_memory(
        {
            "commit_sha": commit,
            "branch": "main",
            "file_path": "app.py",
            "file_sha256": digest,
        },
        repo_path=repo,
        now=datetime(2026, 7, 23, tzinfo=UTC),
    )
    assert result.status == "verified"
    assert result.last_verified_commit == commit
    assert result.refreshed_provenance["branch"] == "main"


def test_verify_memory_marks_changed_file_contradicted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    old_digest = hashlib.sha256((repo / "app.py").read_bytes()).hexdigest()
    (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
    result = verify_memory(
        {"file_path": "app.py", "file_sha256": old_digest},
        repo_path=repo,
    )
    assert result.status == "contradicted"
    assert "changed" in result.contradictions[0]


def test_verify_memory_marks_advanced_commit_stale(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    old_commit = _git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "advance")
    result = verify_memory({"commit_sha": old_commit}, repo_path=repo)
    assert result.status == "stale"
    assert result.last_verified_commit == _git(repo, "rev-parse", "HEAD")


def test_verify_memory_marks_missing_repository_source() -> None:
    result = verify_memory({"commit_sha": "abc"}, repo_path="/definitely/missing/repository")
    assert result.status == "missing_source"


def test_repository_state_supersedes_without_deleting_history(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    verification = verify_memory(
        {"branch": "main", "commit_sha": _git(repo, "rev-parse", "HEAD")},
        repo_path=repo,
    )
    memory = {"metadata": {"repository_state": {"commit_sha": "old"}}}
    grounded = prefer_repository_state(memory, verification)
    assert grounded["metadata"]["repository_state"]["commit_sha"] == verification.last_verified_commit
    assert grounded["metadata"]["verification_history"] == [{"commit_sha": "old"}]


def test_search_wrapper_attaches_verification_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    commit = _git(repo, "rev-parse", "HEAD")

    def original_search(**_kwargs: Any) -> dict[str, Any]:
        return {"status": "ok", "matches": [{"id": "m1", "commit_sha": commit}]}

    module = SimpleNamespace(search_semantic_memory=original_search)
    tool = build_verified_search_tool(module)
    result = tool(query="state", repo_path=str(repo))
    assert result["repository_grounded"] is True
    assert result["verification_counts"] == {"verified": 1}
    assert result["matches"][0]["verification"]["status"] == "verified"
