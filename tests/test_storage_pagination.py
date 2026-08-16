from __future__ import annotations

from pathlib import Path

import pytest

from persistent_memory_mcp.pagination import InvalidCursorError, PaginationError
from persistent_memory_mcp.storage import SQLiteStorage


STAMP = "2026-08-16T04:15:00+00:00"


def _storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Pagination",
            "slug": "pagination",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "projects",
        {
            "id": "project-2",
            "owner_id": "owner-2",
            "name": "Foreign",
            "slug": "foreign",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return storage


def _bulk_tasks(storage: SQLiteStorage, count: int = 2_000) -> None:
    rows = [
        (
            f"task-{index:04d}",
            "project-1",
            "owner-1",
            f"Task {index}",
            "pending",
            "medium",
            "",
            "internal",
            "{}",
            STAMP,
            STAMP,
        )
        for index in range(count)
    ]
    with storage.connect() as connection:
        connection.executemany(
            "insert into tasks("
            "id, project_id, owner_id, title, status, priority, details, sensitivity, "
            "metadata, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()


def test_keyset_walks_thousands_of_same_timestamp_rows_without_gaps(
    tmp_path: Path,
) -> None:
    storage = _storage(tmp_path)
    _bulk_tasks(storage)

    seen: list[str] = []
    cursor: str | None = None
    page_count = 0
    while True:
        page = storage.select_page(
            "tasks",
            {"owner_id": "owner-1", "project_id": "project-1"},
            limit=137,
            cursor=cursor,
        )
        page_count += 1
        seen.extend(str(item["id"]) for item in page.items)
        if not page.has_more:
            assert page.next_cursor is None
            break
        assert page.next_cursor
        cursor = page.next_cursor

    assert page_count == 15
    assert len(seen) == 2_000
    assert len(set(seen)) == 2_000
    assert seen[0] == "task-1999"
    assert seen[-1] == "task-0000"


def test_cursor_anchor_excludes_rows_inserted_after_first_page(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    _bulk_tasks(storage, 200)

    first = storage.select_page(
        "tasks",
        {"owner_id": "owner-1", "project_id": "project-1"},
        limit=25,
    )
    assert first.has_more is True
    assert first.next_cursor

    storage.insert(
        "tasks",
        {
            "id": "task-0170-new",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Inserted after traversal started",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )

    seen = [str(item["id"]) for item in first.items]
    cursor = first.next_cursor
    while cursor:
        page = storage.select_page(
            "tasks",
            {"owner_id": "owner-1", "project_id": "project-1"},
            limit=25,
            cursor=cursor,
        )
        seen.extend(str(item["id"]) for item in page.items)
        cursor = page.next_cursor

    assert len(seen) == 200
    assert "task-0170-new" not in seen
    fresh = storage.select_page(
        "tasks",
        {"owner_id": "owner-1", "project_id": "project-1"},
        limit=200,
    )
    assert any(item["id"] == "task-0170-new" for item in fresh.items)


def test_cursor_is_bound_to_filters_and_query_shape(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    _bulk_tasks(storage, 80)
    storage.insert(
        "tasks",
        {
            "id": "foreign-task",
            "project_id": "project-2",
            "owner_id": "owner-2",
            "title": "Foreign",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )

    page = storage.select_page(
        "tasks",
        {"owner_id": "owner-1", "project_id": "project-1"},
        limit=10,
    )
    assert page.next_cursor

    with pytest.raises(InvalidCursorError, match="does not match"):
        storage.select_page(
            "tasks",
            {"owner_id": "owner-2", "project_id": "project-2"},
            limit=10,
            cursor=page.next_cursor,
        )
    with pytest.raises(InvalidCursorError, match="does not match"):
        storage.select_page(
            "tasks",
            {"owner_id": "owner-1", "project_id": "project-1"},
            limit=10,
            cursor=page.next_cursor,
            descending=False,
        )


def test_malformed_cursor_and_unsafe_columns_fail_closed(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    _bulk_tasks(storage, 5)

    with pytest.raises(InvalidCursorError):
        storage.select_page("tasks", cursor="not-a-cursor")
    with pytest.raises(ValueError, match="order column"):
        storage.select_page("tasks", order_by='created_at"; drop table tasks;--')
    with pytest.raises(ValueError, match="filter column"):
        storage.select_page("tasks", {'owner_id"; drop table tasks;--': "owner-1"})

    assert len(storage.select("tasks")) == 5


def test_page_size_has_conservative_hard_maximum(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    with pytest.raises(PaginationError, match="between 1 and 200"):
        storage.select_page("tasks", limit=201)
    with pytest.raises(PaginationError, match="between 1 and 200"):
        storage.select_page("tasks", limit=0)


def test_ascending_keyset_order_is_deterministic(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    _bulk_tasks(storage, 60)
    first = storage.select_page("tasks", limit=17, descending=False)
    second = storage.select_page(
        "tasks",
        limit=17,
        descending=False,
        cursor=first.next_cursor,
    )
    assert [item["id"] for item in first.items] == [f"task-{index:04d}" for index in range(17)]
    assert second.items[0]["id"] == "task-0017"
