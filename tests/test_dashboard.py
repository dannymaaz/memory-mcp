from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from persistent_memory_mcp.dashboard import (
    DashboardConfig,
    build_handler,
    dashboard_snapshot,
    export_snapshot,
    render_dashboard,
)
from persistent_memory_mcp.storage import SQLiteStorage


def _storage_with_tasks(tmp_path) -> tuple[SQLiteStorage, dict[str, object], dict[str, object]]:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    workspace = storage.insert("workspaces", {"owner_id": "owner-1", "name": "Local", "slug": "local"})
    first = storage.insert(
        "projects",
        {"workspace_id": workspace["id"], "owner_id": "owner-1", "name": "First", "slug": "first"},
    )
    second = storage.insert(
        "projects",
        {"workspace_id": workspace["id"], "owner_id": "owner-1", "name": "Second", "slug": "second"},
    )
    storage.insert(
        "tasks",
        {"project_id": first["id"], "owner_id": "owner-1", "title": "Searchable task", "status": "pending"},
    )
    storage.insert(
        "tasks",
        {"project_id": first["id"], "owner_id": "owner-1", "title": "Other task", "status": "pending"},
    )
    storage.insert(
        "tasks",
        {"project_id": second["id"], "owner_id": "owner-1", "title": "Foreign task", "status": "pending"},
    )
    storage.insert(
        "file_memory",
        {
            "project_id": first["id"],
            "owner_id": "owner-1",
            "file_path": "src/server.py",
            "summary": "Dashboard server",
            "symbols": ["build_handler", "dashboard_snapshot"],
        },
    )
    storage.insert(
        "file_memory",
        {
            "project_id": first["id"],
            "owner_id": "owner-1",
            "file_path": "tests/test_server.py",
            "summary": "Dashboard tests",
            "symbols": ["test_dashboard_http_endpoints_and_security_headers"],
        },
    )
    storage.insert(
        "file_relations",
        {
            "project_id": first["id"],
            "owner_id": "owner-1",
            "source_file": "src/server.py",
            "target_file": "tests/test_server.py",
            "relation_type": "tested_by",
        },
    )
    return storage, first, second


def _add_foreign_owner(storage: SQLiteStorage) -> dict[str, object]:
    workspace = storage.insert(
        "workspaces",
        {"owner_id": "owner-2", "name": "Foreign", "slug": "foreign-owner"},
    )
    project = storage.insert(
        "projects",
        {
            "workspace_id": workspace["id"],
            "owner_id": "owner-2",
            "name": "Foreign project",
            "slug": "foreign-project",
        },
    )
    storage.insert(
        "tasks",
        {
            "project_id": project["id"],
            "owner_id": "owner-2",
            "title": "Foreign owner private task",
            "status": "blocked",
        },
    )
    return project


def _serve(storage: SQLiteStorage, *, owner_id: str | None = None):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        build_handler(storage, row_limit=10, owner_id=owner_id),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_dashboard_rejects_remote_binding(tmp_path) -> None:
    config = DashboardConfig(host="0.0.0.0", sqlite_path=tmp_path / "memory.db")
    with pytest.raises(ValueError, match="localhost"):
        config.validate()


def test_dashboard_rejects_empty_explicit_owner(tmp_path) -> None:
    config = DashboardConfig(owner_id="   ", sqlite_path=tmp_path / "memory.db")
    with pytest.raises(ValueError, match="owner_id"):
        config.validate()


def test_dashboard_snapshot_is_bounded_and_hides_database_path(tmp_path) -> None:
    storage, _, _ = _storage_with_tasks(tmp_path)
    snapshot = dashboard_snapshot(storage, limit=1, tables=("tasks",))
    assert snapshot["read_only"] is True
    assert snapshot["counts"]["tasks"] == 3
    assert len(snapshot["tables"]["tasks"]) == 1
    assert "database" not in snapshot


def test_dashboard_filters_project_table_and_query(tmp_path) -> None:
    storage, first, _ = _storage_with_tasks(tmp_path)
    snapshot = dashboard_snapshot(
        storage,
        limit=10,
        project_id=str(first["id"]),
        tables=("tasks",),
        query="searchable",
    )
    assert list(snapshot["tables"]) == ["tasks"]
    assert snapshot["counts"]["tasks"] == 2
    assert [row["title"] for row in snapshot["tables"]["tasks"]] == ["Searchable task"]


def test_dashboard_rejects_unknown_tables_and_long_queries(tmp_path) -> None:
    storage, _, _ = _storage_with_tasks(tmp_path)
    with pytest.raises(ValueError, match="unsupported"):
        dashboard_snapshot(storage, tables=("secrets",))
    with pytest.raises(ValueError, match="at most"):
        dashboard_snapshot(storage, query="x" * 201)


def test_dashboard_exports_only_bounded_snapshot(tmp_path) -> None:
    storage, _, _ = _storage_with_tasks(tmp_path)
    snapshot = dashboard_snapshot(storage, limit=1, tables=("tasks",))
    json_payload, json_type = export_snapshot(snapshot, export_format="json")
    csv_payload, csv_type = export_snapshot(snapshot, export_format="csv")
    assert json_type.startswith("application/json")
    assert len(json.loads(json_payload)["tables"]["tasks"]) == 1
    assert csv_type.startswith("text/csv")
    assert b"table,record" in csv_payload


def test_dashboard_html_escapes_stored_content() -> None:
    rendered = render_dashboard(
        {
            "counts": {"tasks": 1},
            "tables": {"tasks": [{"title": "<script>alert(1)</script>"}]},
            "filters": {"query": "\"><img src=x>", "project_id": None},
        }
    )
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<img src=x>" not in rendered


def test_dashboard_http_endpoints_and_security_headers(tmp_path) -> None:
    storage, first, _ = _storage_with_tasks(tmp_path)
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/api/snapshot?tables=tasks&project_id={first['id']}&limit=1", timeout=5) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert len(payload["tables"]["tasks"]) == 1
        with urlopen(f"{base}/api/graph?project_id={first['id']}&limit=10", timeout=5) as response:
            graph = json.loads(response.read())
            assert response.status == 200
            assert any(edge["relation"] == "tested_by" for edge in graph["edges"])
            assert any(node["kind"] == "symbol" for node in graph["nodes"])
            assert len(graph["nodes"]) <= 10
            assert graph["limits"] == {"max_nodes": 10, "max_edges": 30}
        project_node_id = f"projects:{first['id']}"
        with urlopen(
            f"{base}/api/graph/context?project_id={first['id']}&select={project_node_id}", timeout=5
        ) as response:
            context = json.loads(response.read())
            assert response.status == 200
            assert context["read_only"] is True
            assert context["selection"] == [project_node_id]
            assert context["nodes"]
        with urlopen(f"{base}/export.csv?tables=tasks&limit=1", timeout=5) as response:
            assert response.headers.get_content_type() == "text/csv"
            assert b"table,record" in response.read()
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/snapshot?tables=secrets", timeout=5)
        assert exc_info.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_operational_http_infers_single_owner_and_stays_bounded(tmp_path) -> None:
    storage, first, _ = _storage_with_tasks(tmp_path)
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/api/operational/projects?limit=1", timeout=5) as response:
            overview = json.loads(response.read())
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert overview["read_only"] is True
            assert len(overview["projects"]) == 1
            assert "owner_id" not in json.dumps(overview)
        with urlopen(
            f"{base}/api/operational/graph?project_id={first['id']}&limit=5", timeout=5
        ) as response:
            graph = json.loads(response.read())
            assert graph["read_only"] is True
            assert len(graph["nodes"]) <= 5
            assert len(graph["edges"]) <= 15
            assert all("details" not in node for node in graph["nodes"])
        with urlopen(
            f"{base}/api/operational/export.json?project_id={first['id']}&limit=4", timeout=5
        ) as response:
            exported = json.loads(response.read())
            assert len(exported["nodes"]) <= 4
        with urlopen(f"{base}/galaxy/operational?project_id={first['id']}&limit=5", timeout=5) as response:
            html_payload = response.read().decode()
            assert response.headers.get_content_type() == "text/html"
            assert "script-src 'unsafe-inline'" in response.headers["Content-Security-Policy"]
            assert "Operational Galaxy" in html_payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_operational_http_requires_explicit_owner_for_multi_owner_database(tmp_path) -> None:
    storage, _, _ = _storage_with_tasks(tmp_path)
    _add_foreign_owner(storage)
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/operational/projects", timeout=5)
        assert exc_info.value.code == 400
        assert "multiple owners" in exc_info.value.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_operational_http_owner_scope_blocks_foreign_project(tmp_path) -> None:
    storage, first, _ = _storage_with_tasks(tmp_path)
    foreign = _add_foreign_owner(storage)
    server, thread = _serve(storage, owner_id="owner-1")
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/api/operational/projects", timeout=5) as response:
            overview = json.loads(response.read())
            ids = {item["project_id"] for item in overview["projects"]}
            assert str(first["id"]) in ids
            assert str(foreign["id"]) not in ids
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/operational/graph?project_id={foreign['id']}", timeout=5)
        assert exc_info.value.code == 400
        assert "owner scope" in exc_info.value.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_operational_graph_requires_project_and_valid_boolean(tmp_path) -> None:
    storage, _, _ = _storage_with_tasks(tmp_path)
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/operational/graph", timeout=5)
        assert exc_info.value.code == 400
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/operational/projects?changed_only=maybe", timeout=5)
        assert exc_info.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
