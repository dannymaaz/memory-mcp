from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from persistent_memory_mcp.dashboard import (
    build_handler,
    dashboard_table_page,
    render_dashboard,
)
from persistent_memory_mcp.maintenance import BackupService
from persistent_memory_mcp.storage import SQLiteStorage


STAMP = "2026-08-16T05:10:00+00:00"


def _storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Dashboard",
            "slug": "dashboard",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return storage


def _serve(
    storage: SQLiteStorage,
    *,
    owner_id: str | None = "owner-1",
    backup_directory: Path | None = None,
):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        build_handler(
            storage,
            row_limit=50,
            owner_id=owner_id,
            backup_directory=backup_directory,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_maintenance_status_endpoint_is_bounded_and_has_security_headers(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    BackupService(storage.path).create_backup(backup_dir / "verified.db")
    server, thread = _serve(storage, backup_directory=backup_dir)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(
            f"{base}/api/maintenance/status?project_id=project-1",
            timeout=5,
        ) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert payload["health"]["status"] == "healthy"
            assert payload["backup"]["configured"] is True
            assert payload["backup"]["latest_verified"]["backup_name"] == "verified.db"
            assert payload["read_only"] is True
            serialized = json.dumps(payload)
            assert str(storage.path) not in serialized
            assert str(backup_dir) not in serialized
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_root_renders_maintenance_cards_and_accessible_empty_state(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/?project_id=project-1", timeout=5) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert "Maintenance status" in body
            assert "Maintenance ready" in body
            assert "Evidence risk" in body
            assert "Sensitivity-tagged" in body
            assert "Maintenance JSON" in body
            assert 'class="empty" role="status">No records yet.' in body
            assert str(storage.path) not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_maintenance_status_rejects_foreign_project(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
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
    server, thread = _serve(storage, owner_id="owner-1")
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(HTTPError) as exc_info:
            urlopen(
                f"{base}/api/maintenance/status?project_id=project-2",
                timeout=5,
            )
        assert exc_info.value.code == 400
        error_body = exc_info.value.read().decode("utf-8")
        assert str(storage.path) not in error_body
        assert str(tmp_path) not in error_body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_root_renders_bounded_error_card_when_owner_is_ambiguous(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
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
    server, thread = _serve(storage, owner_id=None)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/", timeout=5) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert 'role="alert"' in body
            assert "Status unavailable" in body
            assert "multiple owners" in body
            assert str(storage.path) not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_projects_pagination_honors_project_id_scope(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    storage.insert(
        "projects",
        {
            "id": "project-extra",
            "owner_id": "owner-1",
            "name": "Extra",
            "slug": "extra",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    page = dashboard_table_page(
        storage,
        table="projects",
        project_id="project-1",
        owner_id="owner-1",
        limit=10,
    )
    assert page["total_count"] == 1
    assert [row["id"] for row in page["records"]] == ["project-1"]


def test_snapshot_only_table_does_not_render_broken_pagination_link() -> None:
    snapshot = {
        "counts": {"deployment_records": 0},
        "tables": {"deployment_records": []},
        "filters": {"project_id": None, "query": ""},
    }
    body = render_dashboard(snapshot, {"status": "healthy", "health": {}, "storage": {}, "backup": {}, "verification": {}, "sensitivity": {}})
    assert "deployment_records" in body
    assert "Snapshot only" in body
    assert "/api/table-page?table=deployment_records" not in body
