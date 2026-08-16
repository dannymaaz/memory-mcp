from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from persistent_memory_mcp.continuation_contract import (
    CONTINUATION_VERSION,
    build_continuation_snapshot,
    install_continuation_contract,
)
from persistent_memory_mcp.session_lifecycle import install_session_lifecycle


class RepoContext:
    def __init__(self, **values: Any) -> None:
        self.values = values

    def to_dict(self) -> dict[str, Any]:
        return dict(self.values)


class FakeServer:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}


def _fake_module(projects: list[dict[str, Any]] | None = None) -> SimpleNamespace:
    rows: dict[str, list[dict[str, Any]]] = {
        "projects": list(projects or []),
        "sessions": [
            {
                "id": "session-1",
                "project_id": "project-1",
                "interface": "codex",
                "model_name": "gpt",
                "status": "active",
                "created_at": "2026-08-16T03:30:00+00:00",
                "metadata": {"current_goal": "Finish continuation"},
            }
        ],
        "session_state": [
            {
                "session_id": "session-1",
                "project_id": "project-1",
                "state": {
                    "what_was_done": "Implemented resolver",
                    "remaining_work": ["Add tests", "Update docs"],
                    "blockers": ["CI pending"],
                    "files": ["src/server.py", "tests/test_server.py"],
                    "tests": [{"name": "pytest", "status": "passed"}],
                    "next_step": "Run api_key=abcdefghijk validation",
                },
            }
        ],
        "checkpoints": [],
    }
    calls: list[dict[str, Any]] = []

    def table_select(
        _client: Any,
        table: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        values = rows.get(table, [])
        if not filters:
            return list(values)
        return [
            row
            for row in values
            if all(row.get(key) == value for key, value in filters.items())
        ]

    def table_upsert(
        _client: Any,
        table: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        current = dict(payload)
        existing = rows.setdefault(table, [])
        key = current.get("id")
        if key:
            prior = next((row for row in existing if row.get("id") == key), {})
            current = {**prior, **current}
            existing[:] = [row for row in existing if row.get("id") != key]
        existing.append(current)
        return current

    def original_resolve(
        _client: Any,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        calls.append(dict(kwargs))
        project_id = kwargs.get("project_id") or "created-project"
        project = next(
            (row for row in rows["projects"] if row.get("id") == project_id),
            None,
        )
        if project is None:
            project = {
                "id": project_id,
                "owner_id": kwargs.get("owner_id") or "owner-1",
                "repo_path": "/work/current",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            }
            rows["projects"].append(project)
        repo = {
            "repo_root": "/work/current",
            "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            "repo_branch": "main",
            "repo_commit": "abc123",
            "repo_status": [" M src/server.py"],
        }
        return project, {"id": "workspace-1"}, repo

    def original_create(**kwargs: Any) -> dict[str, Any]:
        payload = {
            "id": "session-new",
            "project_id": kwargs.get("project_id") or "project-1",
            "interface": kwargs.get("interface") or "codex",
            "model_name": kwargs.get("model_name") or "gpt",
            "status": "active",
            "created_at": "2026-08-16T04:00:00+00:00",
            "metadata": {"current_goal": kwargs.get("current_goal", "")},
        }
        rows["sessions"].append(payload)
        return {
            "status": "ok",
            "project_id": payload["project_id"],
            "session_id": payload["id"],
            "interface": payload["interface"],
            "model_name": payload["model_name"],
        }

    def original_end(**kwargs: Any) -> dict[str, Any]:
        session_id = kwargs.get("session_id")
        for session in rows["sessions"]:
            if session.get("id") == session_id:
                session["status"] = "ended"
        checkpoint = {
            "id": "checkpoint-1",
            "project_id": kwargs.get("project_id"),
            "owner_id": kwargs.get("owner_id") or "owner-1",
            "metadata": {"interface": "codex"},
        }
        rows["checkpoints"] = [checkpoint]
        return {
            "status": "ok",
            "session_id": session_id,
            "checkpoint_id": "checkpoint-1",
            "next_step": kwargs.get("next_step", ""),
        }

    def original_sync(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "session_id": kwargs.get("session_id"),
            "state_keys": sorted((kwargs.get("state") or {}).keys()),
        }

    def original_resume(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "resume": {
                "project_id": kwargs.get("project_id") or "project-1",
                "what_was_done": "Historical summary",
                "what_is_left": ["Historical pending"],
                "warnings": [],
                "next_step": "Historical next",
                "repo": {
                    "repo_root": "/work/current",
                    "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
                    "repo_branch": "main",
                    "repo_commit": "abc123",
                    "repo_status": [],
                },
            },
        }

    module = SimpleNamespace(
        server=FakeServer(),
        TOOL_HANDLERS={
            "create_session": original_create,
            "end_session": original_end,
            "sync_session_state": original_sync,
            "resume_project": original_resume,
        },
        _resolve_or_create_project=original_resolve,
        create_session=original_create,
        end_session=original_end,
        sync_session_state=original_sync,
        resume_project=original_resume,
        _client=lambda _owner=None: object(),
        _table_select=table_select,
        _table_upsert=table_upsert,
        _find_active_session=lambda _client, project_id: next(
            (
                row
                for row in rows["sessions"]
                if row.get("project_id") == project_id and row.get("status") == "active"
            ),
            None,
        ),
        _sort_rows=lambda values: list(reversed(values)),
        _now_iso=lambda: "2026-08-16T04:00:00+00:00",
        detect_interface=lambda: "codex",
        detect_repo_context=lambda _path=None: RepoContext(
            repo_root="/work/current",
            repo_name="renamed-local-folder",
            repo_slug="renamed-local-folder",
            repo_remote="git@github.com:dannymaaz/memory-mcp.git",
            repo_branch="main",
            repo_commit="abc123",
            repo_status=[" M src/server.py"],
            repo_provider="github",
        ),
    )
    module.server._tools = {
        "create_session": original_create,
        "end_session": original_end,
        "sync_session_state": original_sync,
        "resume_project": original_resume,
    }
    module._rows = rows
    module._calls = calls
    return module


def test_build_continuation_snapshot_is_bounded_and_redacts_secrets() -> None:
    snapshot = build_continuation_snapshot(
        session={"metadata": {"current_goal": "Ship release"}},
        state={
            "files": [f"file-{index}.py" for index in range(30)],
            "next_step": "Use api_key=abcdefghijk for test",
        },
        repo={
            "repo_root": "/Users/example/private/repo",
            "repo_remote": "https://github.com/example/repo.git",
            "repo_branch": "main",
            "repo_commit": "deadbeef",
            "repo_status": [" M app.py"],
        },
    )
    assert snapshot["version"] == CONTINUATION_VERSION
    assert len(snapshot["files"]) == 20
    assert "abcdefghijk" not in snapshot["next_action"]
    assert snapshot["git"]["dirty"] is True
    assert snapshot["git"]["remote"] == "github.com/example/repo"
    assert "/Users/example/private/repo" not in str(snapshot)
    assert len(snapshot["git"]["root_fingerprint"]) == 16


def test_repository_binding_reuses_project_even_when_local_slug_changes() -> None:
    module = _fake_module(
        [
            {
                "id": "project-1",
                "owner_id": "owner-1",
                "slug": "old-name",
                "repo_path": "/work/old-folder",
                "repo_remote": "https://github.com/dannymaaz/memory-mcp.git",
            }
        ]
    )
    install_continuation_contract(module)
    project, _, _ = module._resolve_or_create_project(object(), owner_id="owner-1")
    assert project["id"] == "project-1"
    assert module._calls[-1]["project_id"] == "project-1"
    assert module._calls[-1]["create_if_missing"] is False


def test_repository_binding_is_owner_scoped() -> None:
    module = _fake_module(
        [
            {
                "id": "foreign-project",
                "owner_id": "owner-2",
                "repo_path": "/work/current",
                "repo_remote": "https://github.com/dannymaaz/memory-mcp.git",
            }
        ]
    )
    install_continuation_contract(module)
    project, _, _ = module._resolve_or_create_project(object(), owner_id="owner-1")
    assert project["id"] == "created-project"
    assert module._calls[-1]["project_id"] is None


def test_ambiguous_repository_binding_fails_closed() -> None:
    module = _fake_module(
        [
            {
                "id": "project-a",
                "owner_id": "owner-1",
                "repo_path": "/work/a",
                "repo_remote": "https://github.com/dannymaaz/memory-mcp.git",
            },
            {
                "id": "project-b",
                "owner_id": "owner-1",
                "repo_path": "/work/b",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            },
        ]
    )
    install_continuation_contract(module)
    with pytest.raises(ValueError, match="Ambiguous repository binding"):
        module._resolve_or_create_project(object(), owner_id="owner-1")


def test_end_session_enriches_existing_checkpoint_without_creating_second_one() -> None:
    module = _fake_module(
        [
            {
                "id": "project-1",
                "owner_id": "owner-1",
                "repo_path": "/work/current",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            }
        ]
    )
    install_continuation_contract(module)
    result = module.end_session(
        session_id="session-1",
        project_id="project-1",
        owner_id="owner-1",
    )
    assert result["status"] == "ok"
    assert len(module._rows["checkpoints"]) == 1
    continuation = module._rows["checkpoints"][0]["metadata"]["continuation"]
    assert continuation["objective"] == "Finish continuation"
    assert continuation["completed"] == "Implemented resolver"
    assert continuation["pending"] == ["Add tests", "Update docs"]
    assert continuation["files"] == ["src/server.py", "tests/test_server.py"]
    assert continuation["tests"] == [{"name": "pytest", "status": "passed"}]
    assert continuation["git"]["commit"] == "abc123"
    assert continuation["git"]["dirty"] is True
    assert "abcdefghijk" not in continuation["next_action"]
    assert result["continuation"] == continuation


def test_resume_project_returns_persisted_continuation_compatibly() -> None:
    module = _fake_module(
        [
            {
                "id": "project-1",
                "owner_id": "owner-1",
                "repo_path": "/work/current",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            }
        ]
    )
    install_continuation_contract(module)
    module.end_session(
        session_id="session-1",
        project_id="project-1",
        owner_id="owner-1",
    )
    result = module.resume_project(project_id="project-1", owner_id="owner-1")
    assert result["resume"]["what_was_done"] == "Historical summary"
    assert result["resume"]["continuation_version"] == CONTINUATION_VERSION
    assert result["resume"]["continuation"]["objective"] == "Finish continuation"
    assert result["resume"]["continuation"]["next_action"] == (
        "Run [REDACTED:generic_secret] validation"
    )


def test_handoff_uses_continuation_enhanced_end_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_SESSION_IDLE_MINUTES", "120")
    module = _fake_module(
        [
            {
                "id": "project-1",
                "owner_id": "owner-1",
                "repo_path": "/work/current",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            }
        ]
    )
    install_continuation_contract(module)
    install_session_lifecycle(module)

    result = module.create_session(
        project_id="project-1",
        owner_id="owner-1",
        interface="claude",
        current_goal="Continue in Claude",
    )

    assert result["status"] == "ok"
    assert result["handoff"] is True
    assert len(module._rows["checkpoints"]) == 1
    continuation = module._rows["checkpoints"][0]["metadata"]["continuation"]
    assert continuation["objective"] == "Finish continuation"
    assert continuation["next_action"] == "Continue in Claude"


def test_idle_expiry_uses_continuation_enhanced_end_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_SESSION_IDLE_MINUTES", "120")
    module = _fake_module(
        [
            {
                "id": "project-1",
                "owner_id": "owner-1",
                "repo_path": "/work/current",
                "repo_remote": "git@github.com:dannymaaz/memory-mcp.git",
            }
        ]
    )
    module._rows["sessions"][0]["created_at"] = "2026-08-16T00:00:00+00:00"
    install_continuation_contract(module)
    install_session_lifecycle(module)

    result = module.create_session(
        project_id="project-1",
        owner_id="owner-1",
        interface="codex",
        current_goal="Resume after timeout",
    )

    assert result["status"] == "ok"
    assert result["reused"] is False
    assert len(module._rows["checkpoints"]) == 1
    continuation = module._rows["checkpoints"][0]["metadata"]["continuation"]
    assert continuation["objective"] == "Finish continuation"
    assert continuation["next_action"] == "Resume after timeout"
