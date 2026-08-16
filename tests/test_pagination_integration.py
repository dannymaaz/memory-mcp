from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from persistent_memory_mcp.pagination_integration import install_paginated_reads
from persistent_memory_mcp.storage import SQLiteClient, SQLiteStorage


STAMP = "2026-08-16T04:20:00+00:00"


class FakeMCP:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def tool(self, *, name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        del description

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name] = function
            return function

        return decorator


def _module(tmp_path: Path) -> tuple[SimpleNamespace, SQLiteStorage]:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Pagination integration",
            "slug": "pagination-integration",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    client = SQLiteClient(storage)
    mcp = FakeMCP()

    def original_timeline(
        project_id: str | None = None,
        owner_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return {
            "status": "legacy",
            "project_id": project_id,
            "owner_id": owner_id,
            "limit": limit,
        }

    mcp._tools["get_project_timeline"] = original_timeline
    module = SimpleNamespace(
        server=mcp,
        TOOL_HANDLERS={"get_project_timeline": original_timeline},
        get_project_timeline=original_timeline,
        _client=lambda _owner=None: client,
        _resolve_or_create_project=lambda _client, **_kwargs: (
            {"id": "project-1", "owner_id": "owner-1"},
            {"id": "workspace-1"},
            {},
        ),
    )
    return module, storage


def _timeline_rows(storage: SQLiteStorage, count: int) -> None:
    rows = [
        (
            f"event-{index:04d}",
            "project-1",
            "owner-1",
            "test.event",
            f"Event {index}",
            '{"token":"secret-value"}' if index == count - 1 else "{}",
            STAMP,
            STAMP,
        )
        for index in range(count)
    ]
    with storage.connect() as connection:
        connection.executemany(
            "insert into timeline_events("
            "id, project_id, owner_id, event_type, summary, payload, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.execute(
            "insert into timeline_events("
            "id, project_id, owner_id, event_type, summary, payload, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "foreign-event",
                "project-1",
                "owner-2",
                "foreign",
                "Foreign event",
                "{}",
                STAMP,
                STAMP,
            ),
        )
        connection.commit()


def test_timeline_tool_uses_keyset_page_and_preserves_total_count(tmp_path: Path) -> None:
    module, storage = _module(tmp_path)
    _timeline_rows(storage, 120)
    install_paginated_reads(module)

    first = module.get_project_timeline(
        project_id="project-1",
        owner_id="owner-1",
        limit=25,
    )
    assert first["status"] == "ok"
    assert first["count"] == 120
    assert first["returned_count"] == 25
    assert first["has_more"] is True
    assert first["next_cursor"]
    assert first["timeline"][0]["id"] == "event-0119"
    assert "secret-value" not in str(first)

    second = module.get_project_timeline(
        project_id="project-1",
        owner_id="owner-1",
        limit=25,
        cursor=first["next_cursor"],
    )
    first_ids = {row["id"] for row in first["timeline"]}
    second_ids = {row["id"] for row in second["timeline"]}
    assert first_ids.isdisjoint(second_ids)
    assert second["count"] == 120


def test_generic_history_page_is_registered_and_owner_scoped(tmp_path: Path) -> None:
    module, storage = _module(tmp_path)
    _timeline_rows(storage, 15)
    install_paginated_reads(module)

    assert "list_project_history_page" in module.server._tools
    result = module.list_project_history_page(
        kind="timeline",
        project_id="project-1",
        owner_id="owner-1",
        limit=10,
    )
    assert result["status"] == "ok"
    assert result["returned_count"] == 10
    assert all(row["owner_id"] == "owner-1" for row in result["records"])
    assert all(row["id"] != "foreign-event" for row in result["records"])


def test_generic_history_rejects_unknown_kind(tmp_path: Path) -> None:
    module, _ = _module(tmp_path)
    install_paginated_reads(module)
    result = module.list_project_history_page(kind="secrets", owner_id="owner-1")
    assert result["tool"] == "list_project_history_page"
    assert "kind must be" in result["error"]


def test_remote_timeline_keeps_legacy_call_without_cursor() -> None:
    mcp = FakeMCP()

    def original_timeline(
        project_id: str | None = None,
        owner_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return {"status": "legacy", "project_id": project_id, "owner_id": owner_id, "limit": limit}

    mcp._tools["get_project_timeline"] = original_timeline
    module = SimpleNamespace(
        server=mcp,
        TOOL_HANDLERS={"get_project_timeline": original_timeline},
        get_project_timeline=original_timeline,
        _client=lambda _owner=None: SimpleNamespace(backend_name="supabase"),
    )
    install_paginated_reads(module)

    legacy = module.get_project_timeline(project_id="p", owner_id="o", limit=7)
    assert legacy == {"status": "legacy", "project_id": "p", "owner_id": "o", "limit": 7}
    rejected = module.get_project_timeline(
        project_id="p",
        owner_id="o",
        limit=7,
        cursor="opaque",
    )
    assert rejected["tool"] == "get_project_timeline"
    assert "requires the local SQLite backend" in rejected["error"]
