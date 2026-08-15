from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from persistent_memory_mcp.repository_retrieval import (
    ProgressiveRepositoryRetriever,
    RetrievalLimits,
)


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


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Memory MCP Tests")
    _write(
        repo,
        "src/authentication_helpers.py",
        "def validate_token(token: str) -> bool:\n"
        "    return token.startswith('Bearer ')\n\n"
        "def issue_session(user_id: str) -> str:\n"
        "    return f'session:{user_id}'\n",
    )
    _write(
        repo,
        "src/session_state.py",
        "def resume_session(session_id: str) -> str:\n"
        "    return session_id.strip()\n",
    )
    for index in range(20):
        _write(repo, f"modules/mod_{index:02d}.py", f"def unrelated_{index}():\n    return {index}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo


def _limits(**overrides: int) -> RetrievalLimits:
    values = {
        "max_files": 5,
        "max_symbols": 20,
        "max_neighbors": 4,
        "max_fragments": 4,
        "page_size": 4,
        "max_fragment_lines": 12,
        "token_budget": 1200,
    }
    values.update(overrides)
    return RetrievalLimits(**values)


def test_symbol_only_query_discovers_file_via_local_git_search(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    result = ProgressiveRepositoryRetriever().retrieve(
        str(repo),
        "validate_token",
        limits=_limits(),
        tokenizer="deterministic",
    )

    candidate = next(item for item in result["file_candidates"] if item["path"] == "src/authentication_helpers.py")
    assert "git-grep-content-match" in candidate["reasons"]
    fragment = next(item for item in result["fragments"] if item["symbol"] == "validate_token")
    assert fragment["path"] == "src/authentication_helpers.py"
    assert "def validate_token" in fragment["content"]
    assert fragment["end_line"] - fragment["start_line"] + 1 <= 12


def test_cursor_rejects_dirty_candidate_change_without_commit(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    retriever = ProgressiveRepositoryRetriever()
    limits = _limits(max_files=8, max_symbols=30, page_size=1, max_fragments=1)
    first = retriever.retrieve(
        str(repo),
        "session",
        limits=limits,
        tokenizer="deterministic",
    )
    cursor = first["pagination"]["next_cursor"]
    assert cursor

    session_file = repo / "src/session_state.py"
    session_file.write_text(
        session_file.read_text(encoding="utf-8") + "\ndef dirty_session_change():\n    return True\n",
        encoding="utf-8",
    )
    assert _git(repo, "status", "--porcelain")

    with pytest.raises(ValueError, match="stale|another query"):
        retriever.retrieve(
            str(repo),
            "session",
            cursor=cursor,
            limits=limits,
            tokenizer="deterministic",
        )
