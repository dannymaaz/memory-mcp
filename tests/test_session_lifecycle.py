from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from persistent_memory_mcp.session_lifecycle import (
    install_session_lifecycle,
    session_is_stale,
    session_last_activity,
)


def test_session_last_activity_prefers_metadata() -> None:
    session = {
        "created_at": "2026-07-22T10:00:00+00:00",
        "updated_at": "2026-07-22T11:00:00+00:00",
        "metadata": {"last_activity_at": "2026-07-22T12:00:00+00:00"},
    }
    assert session_last_activity(session) == datetime(2026, 7, 22, 12, tzinfo=UTC)


def test_session_staleness_uses_idle_window() -> None:
    now = datetime(2026, 7, 22, 15, tzinfo=UTC)
    session = {"created_at": (now - timedelta(minutes=121)).isoformat()}
    assert session_is_stale(session, now=now, idle_minutes=120) is True
    assert session_is_stale(session, now=now, idle_minutes=122) is False
    with pytest.raises(ValueError, match="positive"):
        session_is_stale(session, now=now, idle_minutes=0)


class FakeServer:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}


def _fake_module(active: dict[str, Any] | None = None) -> SimpleNamespace:
    rows: dict[str, list[dict[str, Any]]] = {
        "sessions": [active] if active else [],
        "session_state": [],
    }
    calls: dict[str, int] = {"create": 0, "end": 0, "sync": 0}

    def table_select(_client: Any, table: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        values = rows.get(table, [])
        if not filters:
            return values
        return [row for row in values if all(row.get(key) == value for key, value in filters.items())]

    def table_upsert(_client: Any, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = dict(payload)
        current.setdefault("id", "session-1")
        current.setdefault("interface", "codex")
        current.setdefault("model_name", "gpt")
        existing = rows.setdefault(table, [])
        existing[:] = [row for row in existing if row.get("id") != current.get("id")]
        existing.append(current)
        return current

    def original_create(**kwargs: Any) -> dict[str, Any]:
        calls["create"] += 1
        payload = {
            "id": "session-new",
            "project_id": kwargs.get("project_id") or "project-1",
            "interface": kwargs.get("interface") or "codex",
            "model_name": "gpt",
            "status": "active",
            "metadata": {"current_goal": kwargs.get("current_goal", "")},
        }
        rows["sessions"] = [payload]
        return {
            "status": "ok",
            "project_id": payload["project_id"],
            "session_id": payload["id"],
            "interface": payload["interface"],
            "model_name": payload["model_name"],
        }

    def original_end(**_kwargs: Any) -> dict[str, Any]:
        calls["end"] += 1
        rows["sessions"] = []
        return {"status": "ok"}

    def original_sync(**kwargs: Any) -> dict[str, Any]:
        calls["sync"] += 1
        session_id = kwargs.get("session_id")
        if not session_id:
            return {"error": "missing session", "tool": "sync_session_state"}
        return {"status": "ok", "session_id": session_id, "state_keys": []}

    module = SimpleNamespace(
        server=FakeServer(),
        create_session=original_create,
        end_session=original_end,
        sync_session_state=original_sync,
        _client=lambda _owner=None: object(),
        _resolve_or_create_project=lambda *_args, **_kwargs: ({"id": "project-1"}, {}, {}),
        _find_active_session=lambda *_args: rows["sessions"][0] if rows["sessions"] else None,
        _table_select=table_select,
        _table_upsert=table_upsert,
        _now_iso=lambda: "2026-07-22T15:00:00+00:00",
        detect_interface=lambda: "codex",
    )
    module.server._tools = {
        "create_session": original_create,
        "sync_session_state": original_sync,
    }
    module._rows = rows
    module._calls = calls
    return module


def test_reuses_compatible_active_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_SESSION_IDLE_MINUTES", "120")
    active = {
        "id": "session-1",
        "project_id": "project-1",
        "interface": "codex",
        "model_name": "gpt",
        "status": "active",
        "created_at": "2026-07-22T14:30:00+00:00",
        "metadata": {},
    }
    module = _fake_module(active)
    install_session_lifecycle(module)
    result = module.create_session(project_id="project-1", interface="codex", current_goal="Ship PR 7")
    assert result["session_id"] == "session-1"
    assert result["reused"] is True
    assert module._calls["create"] == 0
    assert module.server._tools["create_session"] is module.create_session


def test_sync_auto_creates_and_passes_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_SESSION_IDLE_MINUTES", "120")
    module = _fake_module()
    install_session_lifecycle(module)
    result = module.sync_session_state(project_id="project-1", state={"goal": "test"}, summary="Working")
    assert result["status"] == "ok"
    assert result["session_id"] == "session-new"
    assert result["auto_created"] is True
    assert module._calls == {"create": 1, "end": 0, "sync": 1}


def test_interface_handoff_ends_old_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_SESSION_IDLE_MINUTES", "120")
    active = {
        "id": "session-old",
        "project_id": "project-1",
        "interface": "claude",
        "status": "active",
        "created_at": "2026-07-22T14:30:00+00:00",
        "metadata": {},
    }
    module = _fake_module(active)
    install_session_lifecycle(module)
    result = module.create_session(project_id="project-1", interface="codex")
    assert result["reused"] is False
    assert result["handoff"] is True
    assert module._calls["end"] == 1
    assert module._calls["create"] == 1
