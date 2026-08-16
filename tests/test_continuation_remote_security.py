from __future__ import annotations

from persistent_memory_mcp.continuation_contract import (
    _normalize_remote,
    build_continuation_snapshot,
)


def test_remote_normalization_drops_url_credentials_query_and_fragment() -> None:
    remote = "https://alice:weak-password@github.com/Example/Repo.git?token=hidden#section"
    assert _normalize_remote(remote) == "github.com/example/repo"


def test_scp_and_https_remotes_share_the_same_binding_identity() -> None:
    assert _normalize_remote("git@github.com:Example/Repo.git") == _normalize_remote(
        "https://github.com/example/repo.git"
    )


def test_continuation_snapshot_never_emits_remote_credentials() -> None:
    snapshot = build_continuation_snapshot(
        session=None,
        state={},
        repo={
            "repo_root": "/private/work/repo",
            "repo_remote": "https://alice:weak-password@github.com/Example/Repo.git",
            "repo_branch": "main",
            "repo_commit": "abc123",
            "repo_status": [],
        },
    )
    serialized = str(snapshot)
    assert snapshot["git"]["remote"] == "github.com/example/repo"
    assert "alice" not in serialized
    assert "weak-password" not in serialized
    assert "/private/work/repo" not in serialized
