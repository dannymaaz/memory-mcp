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


def test_dashboard_rejects_remote_binding(tmp_path) -> None:
    config = DashboardConfig(host="0.0.0.0", sqlite_path=tmp_path / "memory.db")
    with pytest.raises(ValueError, match="localhost"):
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
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(storage, row_limit=10))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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
