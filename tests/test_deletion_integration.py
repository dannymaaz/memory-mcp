from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from persistent_memory_mcp.deletion_integration import (
    _USED_PLAN_FINGERPRINTS,
    install_confirmed_deletion,
)


class FakeStorage:
    def __init__(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        self.rows = rows

    def delete_ids(
        self,
        table: str,
        record_ids: tuple[str, ...],
        *,
        owner_id: str,
        project_id: str,
    ) -> int:
        ids = set(record_ids)
        before = len(self.rows.get(table, []))
        self.rows[table] = [
            row
            for row in self.rows.get(table, [])
            if not (
                str(row.get("id")) in ids
                and row.get("owner_id") == owner_id
                and row.get("project_id") == project_id
            )
        ]
        return before - len(self.rows[table])


class FakeServerModule(SimpleNamespace):
    pass


def _make_server() -> tuple[FakeServerModule, dict[str, list[dict[str, Any]]]]:
    rows = {
        "projects": [{"id": "project-1", "owner_id": "owner-a"}],
        "tasks": [
            {
                "id": "task-1",
                "owner_id": "owner-a",
                "project_id": "project-1",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "task-2",
                "owner_id": "owner-a",
                "project_id": "project-1",
                "created_at": "2026-07-25T00:00:00+00:00",
            },
        ],
        "timeline_events": [],
    }
    client = SimpleNamespace(storage=FakeStorage(rows))

    def table_select(_client: Any, table: str, filters: dict[str, Any] | None = None):
        filters = filters or {}
        return [
            dict(row)
            for row in rows.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

    def record_timeline(
        _client: Any,
        project_id: str,
        owner_id: str,
        event_type: str,
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        rows["timeline_events"].append(
            {
                "project_id": project_id,
                "owner_id": owner_id,
                "event_type": event_type,
                "summary": summary,
                "metadata": metadata,
            }
        )

    registered_tools: dict[str, Any] = {}

    def add_tool(function: Any, *, name: str, description: str) -> None:
        assert description
        registered_tools[name] = function

    def remove_tool(name: str) -> None:
        del registered_tools[name]

    server = SimpleNamespace(
        add_tool=add_tool,
        remove_tool=remove_tool,
        registered_tools=registered_tools,
    )
    module = FakeServerModule(
        server=server,
        TOOL_HANDLERS={},
        TOOL_SCHEMAS=[],
        _client=lambda _owner=None: client,
        _resolve_or_create_project=lambda *_args, **_kwargs: (
            {"id": "project-1", "owner_id": "owner-a"},
            {},
            {},
        ),
        _table_select=table_select,
        _record_timeline=record_timeline,
        _use_database_url=lambda: False,
    )
    return module, rows


def test_preview_and_execute_exact_records(monkeypatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "test-secret")
    _USED_PLAN_FINGERPRINTS.clear()
    module, rows = _make_server()
    plan_tool, execute_tool = install_confirmed_deletion(module)

    preview = plan_tool(
        memory_type="tasks",
        project_id="project-1",
        owner_id="owner-a",
        record_ids=["task-1", "missing"],
    )
    assert preview["status"] == "preview"
    assert preview["candidate_count"] == 1
    assert preview["missing_record_ids"] == ["missing"]
    assert len(rows["tasks"]) == 2

    result = execute_tool(
        plan=preview["plan"],
        confirmation_token=preview["confirmation_token"],
        owner_id="owner-a",
    )
    assert result["status"] == "ok"
    assert result["deleted_count"] == 1
    assert [row["id"] for row in rows["tasks"]] == ["task-2"]
    audit = rows["timeline_events"][0]
    assert audit["event_type"] == "memory.deleted"
    assert "content" not in audit["metadata"]


def test_confirmation_token_is_single_use(monkeypatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "test-secret")
    _USED_PLAN_FINGERPRINTS.clear()
    module, _ = _make_server()
    plan_tool, execute_tool = install_confirmed_deletion(module)
    preview = plan_tool(
        memory_type="tasks",
        project_id="project-1",
        owner_id="owner-a",
        record_ids=["task-1"],
    )
    first = execute_tool(preview["plan"], preview["confirmation_token"], "owner-a")
    second = execute_tool(preview["plan"], preview["confirmation_token"], "owner-a")
    assert first["status"] == "ok"
    assert "already been used" in second["error"]


def test_modified_plan_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "test-secret")
    _USED_PLAN_FINGERPRINTS.clear()
    module, rows = _make_server()
    plan_tool, execute_tool = install_confirmed_deletion(module)
    preview = plan_tool(
        memory_type="tasks",
        project_id="project-1",
        owner_id="owner-a",
        record_ids=["task-1"],
    )
    altered = dict(preview["plan"])
    altered["record_ids"] = ["task-1", "task-2"]
    result = execute_tool(altered, preview["confirmation_token"], "owner-a")
    assert "changed" in result["error"]
    assert len(rows["tasks"]) == 2


def test_retention_preview_preserves_recent_record(monkeypatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "test-secret")
    _USED_PLAN_FINGERPRINTS.clear()
    module, _ = _make_server()
    plan_tool, _ = install_confirmed_deletion(module)
    preview = plan_tool(
        memory_type="tasks",
        project_id="project-1",
        owner_id="owner-a",
        retention=True,
        archive_after_days=30,
        keep_recent=1,
    )
    assert preview["status"] == "preview"
    assert preview["plan"]["record_ids"] == ("task-1",)


def test_install_registers_tools() -> None:
    module, _ = _make_server()
    first = install_confirmed_deletion(module)
    second = install_confirmed_deletion(module)
    assert first == second
    assert "plan_memory_deletion" in module.TOOL_HANDLERS
    assert "execute_memory_deletion" in module.TOOL_HANDLERS