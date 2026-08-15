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


@pytest.fixture()
def sample_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Memory MCP Tests")

    _write(
        repo,
        "src/auth.py",
        "\n".join(
            [
                '"""Authentication helpers."""',
                "",
                "import hashlib",
                "",
                "def validate_token(token: str) -> bool:",
                '    """Validate a bearer token without executing external code."""',
                '    example = "sk-proj-abcdefghijklmnop1234567890"',
                "    digest = hashlib.sha256(token.encode()).hexdigest()",
                "    return bool(digest) and token != example",
                "",
                "def issue_session(user_id: str) -> str:",
                "    return f'session:{user_id}'",
                "",
                *[f"# auth context line {index}" for index in range(1, 60)],
            ]
        ),
    )
    _write(
        repo,
        "src/session.ts",
        "export function validateSession(value: string) {\n"
        "  const normalized = value.trim();\n"
        "  return normalized.length > 10;\n"
        "}\n"
        + "\n".join(f"// session context {index}" for index in range(40)),
    )
    _write(
        repo,
        "web/login.js",
        "export function authenticateUser(name) {\n"
        "  return Boolean(name && name.trim());\n"
        "}\n"
        + "\n".join(f"// login context {index}" for index in range(40)),
    )
    _write(
        repo,
        "db/schema.sql",
        "CREATE TABLE sessions (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  token TEXT NOT NULL\n"
        ");\n"
        "CREATE INDEX idx_sessions_token ON sessions(token);\n"
        + "\n".join(f"-- schema context {index}" for index in range(40)),
    )
    _write(repo, "secrets/private.py", "API_KEY = 'super-secret-value-that-must-not-leak'\n")
    for index in range(30):
        _write(
            repo,
            f"modules/module_{index:02d}.py",
            f"def unrelated_{index}():\n    return {index}\n",
        )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo


def _limits(**overrides: int) -> RetrievalLimits:
    values = {
        "max_depth": 4,
        "max_index_files": 200,
        "max_files": 8,
        "max_symbols": 30,
        "max_neighbors": 8,
        "max_fragments": 5,
        "max_file_bytes": 200_000,
        "max_total_bytes": 12_000,
        "max_fragment_lines": 18,
        "page_size": 6,
        "token_budget": 1800,
    }
    values.update(overrides)
    return RetrievalLimits(**values)


def test_symbol_request_returns_bounded_fragment_not_whole_file(sample_repository: Path) -> None:
    retriever = ProgressiveRepositoryRetriever(ignore_patterns=("secrets/**",))
    result = retriever.retrieve(
        str(sample_repository),
        "auth validate_token",
        limits=_limits(),
        tokenizer="deterministic",
    )

    assert result["status"] == "ok"
    assert result["file_candidates"][0]["path"] == "src/auth.py"
    assert result["index"]["files_scanned"] <= 8
    assert result["index"]["files_scanned"] < 34
    assert all(not item["path"].startswith("secrets/") for item in result["file_candidates"])
    assert all(not node["path"].startswith("secrets") for node in result["repository_map"])

    fragment = next(item for item in result["fragments"] if item["symbol"] == "validate_token")
    total_lines = len((sample_repository / "src/auth.py").read_text(encoding="utf-8").splitlines())
    assert fragment["end_line"] - fragment["start_line"] + 1 <= 18
    assert fragment["end_line"] - fragment["start_line"] + 1 < total_lines
    assert "def validate_token" in fragment["content"]
    assert "sk-proj-" not in fragment["content"]
    assert "[REDACTED:openai_key]" in fragment["content"]
    assert len(fragment["content_sha256"]) == 64
    assert len(fragment["file_sha256"]) == 64
    assert fragment["provenance"]["path"] == "src/auth.py"
    assert fragment["provenance"]["commit"] == _git(sample_repository, "rev-parse", "HEAD")
    assert result["token_usage"]["count"] <= result["token_usage"]["budget"] == 1800


def test_typescript_javascript_and_sql_symbols_are_retrievable(sample_repository: Path) -> None:
    retriever = ProgressiveRepositoryRetriever(ignore_patterns=("secrets/**",))
    scenarios = (
        ("session validateSession", "src/session.ts", "validateSession"),
        ("login authenticateUser", "web/login.js", "authenticateUser"),
        ("schema sessions table", "db/schema.sql", "sessions"),
    )
    for query, expected_path, expected_symbol in scenarios:
        result = retriever.retrieve(
            str(sample_repository),
            query,
            limits=_limits(max_files=12, token_budget=2200),
            tokenizer="deterministic",
        )
        assert any(item["path"] == expected_path for item in result["file_candidates"])
        assert any(
            item["path"] == expected_path and item["symbol"] == expected_symbol
            for item in result["fragments"]
        )


def test_cursor_is_deterministic_and_rejected_after_repository_changes(
    sample_repository: Path,
) -> None:
    retriever = ProgressiveRepositoryRetriever(ignore_patterns=("secrets/**",))
    limits = _limits(max_files=20, max_symbols=50, page_size=1, max_fragments=1, token_budget=1200)
    first = retriever.retrieve(
        str(sample_repository),
        "session",
        limits=limits,
        tokenizer="deterministic",
    )
    cursor = first["pagination"]["next_cursor"]
    assert cursor

    second = retriever.retrieve(
        str(sample_repository),
        "session",
        cursor=cursor,
        limits=limits,
        tokenizer="deterministic",
    )
    assert second["pagination"]["offset"] == 1
    assert second["symbol_candidates"] != first["symbol_candidates"]

    _write(sample_repository, "src/new_session.py", "def session_marker():\n    return True\n")
    _git(sample_repository, "add", ".")
    _git(sample_repository, "commit", "-m", "change repository state")
    with pytest.raises(ValueError, match="stale|another query"):
        retriever.retrieve(
            str(sample_repository),
            "session",
            cursor=cursor,
            limits=limits,
            tokenizer="deterministic",
        )


def test_path_traversal_and_limit_validation_fail_closed(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    retriever = ProgressiveRepositoryRetriever()
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe|escapes"):
        retriever._safe_file(sample_repository.resolve(), "../outside.py")

    with pytest.raises(ValueError, match="token_budget"):
        RetrievalLimits(token_budget=255)
    with pytest.raises(ValueError, match="max_depth"):
        RetrievalLimits(max_depth=0)


def test_total_byte_and_token_budgets_are_enforced(sample_repository: Path) -> None:
    retriever = ProgressiveRepositoryRetriever(ignore_patterns=("secrets/**",))
    result = retriever.retrieve(
        str(sample_repository),
        "auth session login schema",
        limits=_limits(
            max_files=12,
            max_fragments=8,
            max_total_bytes=350,
            token_budget=650,
        ),
        tokenizer="deterministic",
    )
    assert sum(item["bytes"] for item in result["fragments"]) <= 350
    assert result["token_usage"]["count"] <= 650
    assert isinstance(result["token_usage"]["truncated_for_budget"], bool)
