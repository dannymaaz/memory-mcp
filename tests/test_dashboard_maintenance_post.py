from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from persistent_memory_mcp.dashboard import build_handler
from persistent_memory_mcp.dashboard_actions import _RESTORE_PLANS
from persistent_memory_mcp.maintenance import BackupService
from persistent_memory_mcp.storage import SQLiteStorage

STAMP = "2026-08-16T06:00:00+00:00"


def _storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Dashboard actions",
            "slug": "dashboard-actions",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return storage


def _serve(
    storage: SQLiteStorage,
    *,
    backup_directory: Path | None = None,
):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        build_handler(
            storage,
            row_limit=50,
            owner_id="owner-1",
            backup_directory=backup_directory,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _post_json(
    base: str,
    path: str,
    payload: dict[str, Any],
    *,
    include_action_header: bool = True,
    content_type: str = "application/json",
) -> tuple[int, dict[str, Any], Any]:
    headers = {"Content-Type": content_type}
    if include_action_header:
        headers["X-Memory-MCP-Action"] = "1"
    request = Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read()), exc.headers
    with response:
        return response.status, json.loads(response.read()), response.headers


def test_post_requires_explicit_action_header_and_json(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    server, thread = _serve(storage, backup_directory=tmp_path / "backups")
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, payload, _headers = _post_json(
            base,
            "/api/maintenance/backup",
            {},
            include_action_header=False,
        )
        assert status == 403
        assert payload["error"] == "action_header_required"

        status, payload, _headers = _post_json(
            base,
            "/api/maintenance/backup",
            {},
            content_type="text/plain",
        )
        assert status == 415
        assert payload["error"] == "json_required"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_backup_post_creates_verified_backup_without_exposing_paths(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    server, thread = _serve(storage, backup_directory=backup_dir)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, payload, headers = _post_json(base, "/api/maintenance/backup", {})
        assert status == 200
        assert payload["status"] == "ok"
        assert payload["integrity_status"] == "ok"
        assert (backup_dir / payload["backup_name"]).is_file()
        assert (backup_dir / payload["manifest_name"]).is_file()
        assert headers["Cache-Control"] == "no-store"
        serialized = json.dumps(payload)
        assert str(tmp_path) not in serialized
        assert str(storage.path) not in serialized
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_restore_http_requires_preview_and_restores_verified_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-http-secret")
    _RESTORE_PLANS.clear()
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    BackupService(storage.path).create_backup(backup_dir / "before.db")
    storage.insert(
        "tasks",
        {
            "id": "task-after-backup",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Restore removes this",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    server, thread = _serve(storage, backup_directory=backup_dir)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, preview, _headers = _post_json(
            base,
            "/api/maintenance/restore/plan",
            {"backup_name": "before.db"},
        )
        assert status == 200
        assert preview["status"] == "preview"
        assert preview["plan_id"]
        assert preview["confirmation_token"]
        assert storage.select("tasks", {"id": "task-after-backup"})

        status, result, _headers = _post_json(
            base,
            "/api/maintenance/restore/execute",
            {
                "plan_id": preview["plan_id"],
                "confirmation_token": preview["confirmation_token"],
            },
        )
        assert status == 200
        assert result["status"] == "ok"
        assert storage.select("tasks", {"id": "task-after-backup"}) == []
        assert str(tmp_path) not in json.dumps(result)

        status, rejected, _headers = _post_json(
            base,
            "/api/maintenance/restore/execute",
            {
                "plan_id": preview["plan_id"],
                "confirmation_token": preview["confirmation_token"],
            },
        )
        assert status == 400
        assert rejected["status"] == "error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_delete_http_preview_confirm_is_scoped_and_single_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONFIRMATION_SECRET", "dashboard-http-secret")
    storage = _storage(tmp_path)
    storage.insert(
        "tasks",
        {
            "id": "task-delete",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Delete through Dashboard",
            "status": "pending",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    server, thread = _serve(storage)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, preview, _headers = _post_json(
            base,
            "/api/maintenance/delete/plan",
            {
                "memory_type": "tasks",
                "project_id": "project-1",
                "record_ids": ["task-delete"],
            },
        )
        assert status == 200
        assert preview["candidate_count"] == 1
        assert storage.select("tasks", {"id": "task-delete"})

        status, result, _headers = _post_json(
            base,
            "/api/maintenance/delete/execute",
            {
                "plan": preview["plan"],
                "confirmation_token": preview["confirmation_token"],
            },
        )
        assert status == 200
        assert result["deleted_count"] == 1
        assert storage.select("tasks", {"id": "task-delete"}) == []

        status, rejected, _headers = _post_json(
            base,
            "/api/maintenance/delete/execute",
            {
                "plan": preview["plan"],
                "confirmation_token": preview["confirmation_token"],
            },
        )
        assert status == 400
        assert rejected["status"] == "error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_root_renders_action_controls_and_same_origin_connect_csp(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    backup_dir = tmp_path / "backups"
    server, thread = _serve(storage, backup_directory=backup_dir)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base}/?project_id=project-1", timeout=5) as response:
            body = response.read().decode("utf-8")
            csp = response.headers["Content-Security-Policy"]
            assert response.status == 200
            assert "Maintenance actions" in body
            assert "Create verified backup" in body
            assert "Preview restore" in body
            assert "Confirm restore" in body
            assert "Preview deletion" in body
            assert "Confirm deletion" in body
            assert 'script-src \'unsafe-inline\'' in csp
            assert "connect-src 'self'" in csp
            assert str(storage.path) not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
