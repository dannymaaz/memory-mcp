from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

import pytest

from persistent_memory_mcp.dashboard import build_handler, dashboard_table_page
from persistent_memory_mcp.pagination import InvalidCursorError
from persistent_memory_mcp.storage import SQLiteStorage


STAMP = "2026-08-16T04:30:00+00:00"


def _storage(tmp_path) -> tuple[SQLiteStorage, str]:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    workspace = storage.insert(
        "workspaces",
        {"owner_id": "owner-1", "name": "Local", "slug": "local"},
    )
    project = storage.insert(
        "projects",
        {
            "id": "project-1",
            "workspace_id": workspace["id"],
            "owner_id": "owner-1",
            "name": "Pagination",
            "slug": "pagination",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    rows = [
        (
            f"task-{index:04d}",
            project["id"],
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
        for index in range(80)
    ]
    with storage.connect() as connection:
        connection.executemany(
            "insert into tasks("
            "id, project_id, owner_id, title, status, priority, details, sensitivity, metadata, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    return storage, str(project["id"])


def _add_foreign_owner(storage: SQLiteStorage) -> str:
    workspace = storage.insert(
        "workspaces",
        {"owner_id": "owner-2", "name": "Foreign", "slug": "foreign"},
    )
    project = storage.insert(
        "projects",
        {
            "id": "project-2",
            "workspace_id": workspace["id"],
            "owner_id": "owner-2",
            "name": "Foreign",
            "slug": "foreign-project",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "tasks",
        {
            "id": "foreign-task",
            "project_id": project["id"],
            "owner_id": "owner-2",
            "title": "Private foreign task",
            "status": "blocked",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return str(project["id"])


def _serve(storage: SQLiteStorage, *, owner_id: str | None = None):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        build_handler(storage, row_limit=100, owner_id=owner_id),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_dashboard_table_page_is_owner_and_project_scoped(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    foreign_project = _add_foreign_owner(storage)

    page = dashboard_table_page(
        storage,
        table="tasks",
        project_id=project_id,
        owner_id="owner-1",
        limit=17,
    )
    assert page["read_only"] is True
    assert page["total_count"] == 80
    assert page["returned_count"] == 17
    assert page["has_more"] is True
    assert page["next_cursor"]
    assert all(row["owner_id"] == "owner-1" for row in page["records"])
    assert all(row["project_id"] == project_id for row in page["records"])

    with pytest.raises(ValueError, match="owner scope"):
        dashboard_table_page(
            storage,
            table="tasks",
            project_id=foreign_project,
            owner_id="owner-1",
            limit=10,
        )


def test_dashboard_table_page_cursor_walk_is_deterministic(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    first = dashboard_table_page(
        storage,
        table="tasks",
        project_id=project_id,
        owner_id="owner-1",
        limit=30,
    )
    second = dashboard_table_page(
        storage,
        table="tasks",
        project_id=project_id,
        owner_id="owner-1",
        limit=30,
        cursor=first["next_cursor"],
    )
    first_ids = [row["id"] for row in first["records"]]
    second_ids = [row["id"] for row in second["records"]]
    assert first_ids[0] == "task-0079"
    assert second_ids[0] == "task-0049"
    assert set(first_ids).isdisjoint(second_ids)
    assert second["total_count"] == 80


def test_dashboard_table_page_fails_closed_for_multi_owner_without_config(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    _add_foreign_owner(storage)
    with pytest.raises(ValueError, match="multiple owners"):
        dashboard_table_page(storage, table="tasks", project_id=project_id, limit=10)


def test_dashboard_http_table_page_returns_cursor_and_security_headers(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    server, thread = _serve(storage, owner_id="owner-1")
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(
            f"{base}/api/table-page?table=tasks&project_id={project_id}&limit=13",
            timeout=5,
        ) as response:
            first = json.loads(response.read())
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert first["returned_count"] == 13
            assert first["next_cursor"]
        cursor = quote(first["next_cursor"], safe="")
        with urlopen(
            f"{base}/api/table-page?table=tasks&project_id={project_id}&limit=13&cursor={cursor}",
            timeout=5,
        ) as response:
            second = json.loads(response.read())
            assert second["returned_count"] == 13
            assert {row["id"] for row in first["records"]}.isdisjoint(
                {row["id"] for row in second["records"]}
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_http_rejects_cross_scope_cursor_and_unsupported_table(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    foreign_project = _add_foreign_owner(storage)
    server, thread = _serve(storage, owner_id="owner-1")
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(
            f"{base}/api/table-page?table=tasks&project_id={project_id}&limit=10",
            timeout=5,
        ) as response:
            first = json.loads(response.read())
        cursor = quote(first["next_cursor"], safe="")
        with pytest.raises(HTTPError) as exc_info:
            urlopen(
                f"{base}/api/table-page?table=tasks&project_id={foreign_project}&cursor={cursor}",
                timeout=5,
            )
        assert exc_info.value.code == 400
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/table-page?table=secrets", timeout=5)
        assert exc_info.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_cursor_is_not_reusable_for_another_table(tmp_path) -> None:
    storage, project_id = _storage(tmp_path)
    page = dashboard_table_page(
        storage,
        table="tasks",
        project_id=project_id,
        owner_id="owner-1",
        limit=10,
    )
    assert page["next_cursor"]
    with pytest.raises(InvalidCursorError, match="does not match"):
        storage.select_page(
            "decisions",
            {"owner_id": "owner-1", "project_id": project_id},
            cursor=page["next_cursor"],
        )
