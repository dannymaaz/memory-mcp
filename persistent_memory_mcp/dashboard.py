"""Local-first operational dashboard with safe read-only defaults."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from .dashboard_maintenance_http import (
    MAX_ACTION_BODY_BYTES,
    dispatch_maintenance_action,
    render_maintenance_controls,
)
from .dashboard_status import DashboardStatusError, DashboardStatusService
from .galaxy_view import render_galaxy_view
from .knowledge_graph import build_knowledge_graph, compact_graph_context
from .operational_map import OperationalMapLimits, OperationalMapService
from .pagination import MAX_PAGE_SIZE
from .security import redact_sensitive_value
from .storage import SQLiteStorage

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_DASHBOARD_TABLES = (
    "projects",
    "sessions",
    "decisions",
    "tasks",
    "warnings",
    "file_memory",
    "file_relations",
    "memory_documents",
    "retention_policies",
    "deployment_records",
)
_MAX_LIMIT = 500
_MAX_QUERY_LENGTH = 200
_OPERATIONAL_PATHS = {
    "/api/operational/projects",
    "/api/operational/graph",
    "/api/operational/export.json",
    "/galaxy/operational",
}


@dataclass(frozen=True)
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    sqlite_path: Path = Path.home() / ".memory-mcp" / "memory.db"
    row_limit: int = 100
    owner_id: str | None = None
    backup_directory: Path | None = None

    def validate(self) -> None:
        if self.host not in _LOOPBACK_HOSTS:
            raise ValueError("dashboard host must be localhost unless remote access is implemented")
        if not 1 <= self.port <= 65535:
            raise ValueError("dashboard port must be between 1 and 65535")
        if not 1 <= self.row_limit <= _MAX_LIMIT:
            raise ValueError(f"dashboard row_limit must be between 1 and {_MAX_LIMIT}")
        if self.owner_id is not None and not self.owner_id.strip():
            raise ValueError("dashboard owner_id cannot be empty when provided")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (table,)
    ).fetchone() is not None


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'pragma table_info("{table}")').fetchall()}


def _order_column(columns: set[str]) -> str:
    for candidate in ("updated_at", "created_at", "started_at", "deployed_at", "id"):
        if candidate in columns:
            return candidate
    return "rowid"


def _pagination_order_column(columns: set[str]) -> str:
    for candidate in ("created_at", "started_at", "deployed_at", "updated_at"):
        if candidate in columns:
            return candidate
    return "rowid"


def _row_matches(row: Mapping[str, Any], query: str) -> bool:
    if not query:
        return True
    return query.casefold() in json.dumps(row, ensure_ascii=False, default=str).casefold()


def _read_table(
    connection: sqlite3.Connection,
    table: str,
    *,
    limit: int,
    project_id: str | None,
    query: str,
) -> tuple[int, list[dict[str, Any]]]:
    if table not in _DASHBOARD_TABLES or not _table_exists(connection, table):
        return 0, []
    columns = _table_columns(connection, table)
    where = ""
    params: list[Any] = []
    if project_id and "project_id" in columns:
        where = ' where "project_id" = ?'
        params.append(project_id)
    count = int(connection.execute(f'select count(*) from "{table}"{where}', params).fetchone()[0])
    candidate_limit = min(_MAX_LIMIT, max(limit, limit * 5 if query else limit))
    order = _order_column(columns)
    rows = connection.execute(
        f'select * from "{table}"{where} order by "{order}" desc limit ?',
        [*params, candidate_limit],
    ).fetchall()
    decoded = [SQLiteStorage._decode_row(row) for row in rows]
    return count, [row for row in decoded if _row_matches(row, query)][:limit]


def dashboard_snapshot(
    storage: SQLiteStorage,
    *,
    limit: int = 100,
    project_id: str | None = None,
    tables: Sequence[str] | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Return a bounded, read-only operational snapshot."""
    if not 1 <= limit <= _MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {_MAX_LIMIT}")
    if len(query) > _MAX_QUERY_LENGTH:
        raise ValueError(f"query must be at most {_MAX_QUERY_LENGTH} characters")
    selected = tuple(tables or _DASHBOARD_TABLES)
    invalid = sorted(set(selected) - set(_DASHBOARD_TABLES))
    if invalid:
        raise ValueError(f"unsupported dashboard table(s): {', '.join(invalid)}")
    result_tables: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    with storage.connect() as connection:
        for table in selected:
            try:
                count, rows = _read_table(
                    connection,
                    table,
                    limit=limit,
                    project_id=project_id,
                    query=query,
                )
            except sqlite3.Error as exc:
                count, rows = 0, []
                errors[table] = str(exc)
            counts[table] = count
            result_tables[table] = rows
    return {
        "backend": storage.backend_name,
        "counts": counts,
        "tables": result_tables,
        "errors": errors,
        "filters": {
            "project_id": project_id,
            "tables": list(selected),
            "query": query,
            "limit": limit,
        },
        "read_only": True,
    }


def _resolve_operational_owner(storage: SQLiteStorage, configured_owner: str | None) -> str:
    configured = str(configured_owner or "").strip()
    if configured:
        return configured
    with storage.connect() as connection:
        rows = connection.execute(
            "select distinct owner_id from projects where owner_id is not null and trim(owner_id) != '' "
            "order by owner_id asc limit 2"
        ).fetchall()
    owners = [str(row[0]) for row in rows]
    if len(owners) == 1:
        return owners[0]
    if not owners:
        raise ValueError("operational owner is not configured and no project owner can be inferred")
    raise ValueError("operational owner must be configured when multiple owners exist")


def dashboard_table_page(
    storage: SQLiteStorage,
    *,
    table: str,
    limit: int = 50,
    cursor: str | None = None,
    project_id: str | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Return one owner-scoped deterministic table page for Dashboard drill-down."""
    if table not in _DASHBOARD_TABLES:
        raise ValueError("unsupported dashboard table")
    if table not in storage.allowed_tables:
        raise ValueError(f"dashboard table {table} does not support keyset pagination")
    owner = _resolve_operational_owner(storage, owner_id)
    page_limit = min(int(limit), MAX_PAGE_SIZE)
    if page_limit < 1:
        raise ValueError("limit must be positive")

    with storage.connect() as connection:
        if not _table_exists(connection, table):
            raise ValueError(f"dashboard table {table} does not exist")
        columns = _table_columns(connection, table)
        filters: dict[str, Any] = {}
        if "owner_id" in columns:
            filters["owner_id"] = owner
        if project_id:
            project_row = connection.execute(
                "select 1 from projects where id=? and owner_id=?",
                (project_id, owner),
            ).fetchone()
            if project_row is None:
                raise ValueError("project does not exist inside the active owner scope")
            if "project_id" in columns:
                filters["project_id"] = project_id
            elif table == "projects" and "id" in columns:
                filters["id"] = project_id
        order_by = _pagination_order_column(columns)
        if order_by == "rowid":
            raise ValueError(f"dashboard table {table} lacks a stable timestamp order column")
        where_sql = ""
        params: list[Any] = []
        if filters:
            where_sql = " where " + " and ".join(f'"{key}" = ?' for key in filters)
            params.extend(filters.values())
        total = int(
            connection.execute(
                f'select count(*) from "{table}"{where_sql}',
                params,
            ).fetchone()[0]
        )

    page = storage.select_page(
        table,
        filters,
        limit=page_limit,
        cursor=cursor,
        order_by=order_by,
        descending=True,
    )
    payload = {
        "table": table,
        "project_id": project_id,
        "records": page.items,
        "total_count": total,
        "returned_count": len(page.items),
        "has_more": page.has_more,
        "next_cursor": page.next_cursor,
        "cursor_version": page.cursor_version,
        "limit": page.limit,
        "order_by": page.order_by,
        "descending": page.descending,
        "read_only": True,
    }
    return redact_sensitive_value(payload).value


def export_snapshot(snapshot: Mapping[str, Any], *, export_format: str) -> tuple[bytes, str]:
    """Export the already-bounded snapshot without exposing local filesystem paths."""
    if export_format == "json":
        return (
            json.dumps(snapshot, ensure_ascii=False, default=str, indent=2).encode(),
            "application/json; charset=utf-8",
        )
    if export_format != "csv":
        raise ValueError("export format must be json or csv")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["table", "record"])
    for table, rows in snapshot.get("tables", {}).items():
        for row in rows:
            writer.writerow([table, json.dumps(row, ensure_ascii=False, default=str)])
    return output.getvalue().encode(), "text/csv; charset=utf-8"


def _format_bytes(value: Any) -> str:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "0 B"


def _maintenance_cards(maintenance: Mapping[str, Any] | None) -> str:
    if not maintenance:
        return '<section class="status error" role="status"><strong>Maintenance status unavailable</strong></section>'
    if maintenance.get("status") == "error":
        message = html.escape(str(maintenance.get("message") or "Maintenance status unavailable"))
        return f'<section class="status error" role="alert"><strong>Status unavailable</strong><p>{message}</p></section>'
    health = maintenance.get("health", {})
    storage = maintenance.get("storage", {})
    backup = maintenance.get("backup", {})
    verification = maintenance.get("verification", {})
    sensitivity = maintenance.get("sensitivity", {})
    backup_info = backup.get("latest_verified") or {}
    backup_label = backup_info.get("backup_name") or (
        "Not configured" if not backup.get("configured") else "None verified"
    )
    sensitivity_total = sum(int(value) for value in (sensitivity.get("totals") or {}).values())
    values = (
        ("Health", health.get("status", "unknown")),
        ("Maintenance ready", "yes" if health.get("maintenance_ready") else "no"),
        ("Database", _format_bytes(storage.get("database_size_bytes"))),
        ("Free disk", _format_bytes(storage.get("disk_free_bytes"))),
        ("Latest backup", backup_label),
        ("Evidence risk", verification.get("evidence_risk_count", 0)),
        ("Sensitivity-tagged", sensitivity_total),
    )
    cards = "".join(
        "<article class=\"maintenance-card\"><strong>"
        + html.escape(str(label))
        + "</strong><span>"
        + html.escape(str(value))
        + "</span></article>"
        for label, value in values
    )
    return (
        '<section class="maintenance" aria-labelledby="maintenance-heading">'
        '<h2 id="maintenance-heading">Maintenance status</h2><div class="cards">'
        + cards
        + "</div></section>"
    )


def render_dashboard(
    snapshot: Mapping[str, Any],
    maintenance: Mapping[str, Any] | None = None,
) -> str:
    """Render a dependency-free dashboard page with escaped content."""
    counts = snapshot.get("counts", {})
    tables = snapshot.get("tables", {})
    filters = snapshot.get("filters", {})
    cards = "".join(
        f"<article><strong>{html.escape(str(name))}</strong><span>{int(value)}</span></article>"
        for name, value in counts.items()
    )
    query = html.escape(str(filters.get("query") or ""), quote=True)
    raw_project = str(filters.get("project_id") or "")
    project = html.escape(raw_project, quote=True)
    sections: list[str] = []
    for name, rows in tables.items():
        body = "".join(
            "<li><code>"
            + html.escape(json.dumps(row, ensure_ascii=False, default=str))
            + "</code></li>"
            for row in rows
        ) or '<li class="empty" role="status">No records yet.</li>'
        page_link = ""
        if name in SQLiteStorage.allowed_tables:
            page_href = f"/api/table-page?table={html.escape(str(name), quote=True)}"
            if project:
                page_href += f"&amp;project_id={project}"
            page_link = f'<a href="{page_href}">Browse paginated JSON</a>'
        else:
            page_link = '<small>Snapshot only</small>'
        sections.append(
            f"<section><h2>{html.escape(str(name))}</h2>"
            f"{page_link}<ol>{body}</ol></section>"
        )
    galaxy_href = "/galaxy" + (f"?project_id={project}" if project else "")
    operational_href = (
        f"/galaxy/operational?project_id={project}" if project else "/api/operational/projects"
    )
    maintenance_href = "/api/maintenance/status" + (f"?project_id={project}" if project else "")
    operational_label = "Operational galaxy" if project else "Operational projects"
    controls = render_maintenance_controls(
        maintenance,
        project_id=raw_project or None,
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        '<title>Persistent Memory MCP Dashboard</title><style>'
        'body{font-family:system-ui,sans-serif;margin:0;background:#0b1220;color:#e5edf8}'
        'main{max-width:1180px;margin:auto;padding:32px}header{margin-bottom:24px}'
        '.cards,.action-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}'
        'article,section,form{background:#121c2e;border:1px solid #26344b;border-radius:12px;padding:16px}'
        'article span{display:block;font-size:1.45rem;margin-top:8px}.maintenance{margin:16px 0}.maintenance .cards{margin-top:12px}'
        '.maintenance-card span{font-size:1.1rem}.status.error{border-color:#a33;color:#ffd3d3}.empty,.muted{color:#9fb0c7}'
        '.maintenance-actions{margin:16px 0}.maintenance-actions article{display:flex;flex-direction:column;gap:10px}'
        '.action-status{white-space:pre-wrap;overflow:auto;background:#0b1220;border:1px solid #26344b;border-radius:8px;padding:12px}'
        'section{margin-top:16px}ol{padding-left:20px}li{margin:8px 0;overflow-wrap:anywhere}code{white-space:pre-wrap}'
        'small{color:#9fb0c7}form{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}'
        'input,select,button,a{padding:10px;border-radius:8px;border:1px solid #41516b;background:#0b1220;color:#e5edf8;text-decoration:none}'
        'button:disabled,input:disabled{opacity:.55;cursor:not-allowed}'
        '</style></head><body><main><header><h1>Persistent Memory MCP</h1>'
        '<small>Local-first operational dashboard; destructive actions require preview and confirmation.</small></header>'
        f'<form method="get"><input name="project_id" placeholder="Project ID" value="{project}">'
        f'<input name="q" placeholder="Search" maxlength="200" value="{query}">'
        '<button type="submit">Filter</button>'
        f'<a href="{galaxy_href}">Open galaxy</a>'
        f'<a href="{operational_href}">{operational_label}</a>'
        f'<a href="{maintenance_href}">Maintenance JSON</a></form>'
        f'{_maintenance_cards(maintenance)}{controls}'
        f'<div class="cards">{cards}</div>{"".join(sections)}</main></body></html>'
    )


def _parse_tables(raw: str | None) -> tuple[str, ...] | None:
    if not raw:
        return None
    values = tuple(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    invalid = sorted(set(values) - set(_DASHBOARD_TABLES))
    if invalid:
        raise ValueError(f"unsupported dashboard table(s): {', '.join(invalid)}")
    return values


def _parse_bool(raw: str | None, *, name: str) -> bool:
    value = str(raw or "").strip().casefold()
    if not value:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _build_graph(
    snapshot: Mapping[str, Any], project_id: str | None, query: str, limit: int
) -> dict[str, Any]:
    return build_knowledge_graph(
        snapshot["tables"],
        project_id=project_id,
        query=query,
        max_nodes=min(limit, 500),
        max_edges=min(limit * 3, 1500),
    )


def _operational_limits(limit: int) -> OperationalMapLimits:
    return OperationalMapLimits(
        max_projects=min(limit, 100),
        max_repositories=min(20, max(1, limit)),
        max_nodes=min(limit, 500),
        max_edges=min(limit * 3, 1500),
        max_records_per_kind=min(limit, 200),
    )


def _operational_payload(
    storage: SQLiteStorage,
    *,
    owner_id: str | None,
    project_id: str | None,
    limit: int,
    verification: str | None,
    risk: str | None,
    changed_only: bool,
) -> dict[str, Any]:
    owner = _resolve_operational_owner(storage, owner_id)
    service = OperationalMapService(storage, owner_id=owner)
    limits = _operational_limits(limit)
    if project_id:
        return service.impact_graph(
            project_id,
            limits=limits,
            verification=verification,
            risk=risk,
            changed_only=changed_only,
        )
    if changed_only:
        raise ValueError("changed_only requires project_id")
    return service.project_overview(
        limits=limits,
        verification=verification,
        risk=risk,
    )


def _maintenance_payload(
    storage: SQLiteStorage,
    *,
    owner_id: str | None,
    backup_directory: Path | None,
    project_id: str | None,
) -> dict[str, Any]:
    return DashboardStatusService(
        storage,
        owner_id=owner_id,
        backup_directory=backup_directory,
    ).read(project_id=project_id)


def build_handler(
    storage: SQLiteStorage,
    *,
    row_limit: int = 100,
    owner_id: str | None = None,
    backup_directory: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def _security_headers(self, *, allow_script: bool = False) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            script = "; script-src 'unsafe-inline'; connect-src 'self'" if allow_script else ""
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'{script}",
            )

        def _send_payload(
            self,
            payload: bytes,
            content_type: str,
            *,
            allow_script: bool = False,
        ) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self._security_headers(allow_script=allow_script)
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, status_code: int, payload: Mapping[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, default=str).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            try:
                requested = int(params.get("limit", [str(row_limit)])[0])
                limit = min(row_limit, max(1, requested))
                query = params.get("q", [""])[0].strip()
                project_id = params.get("project_id", [""])[0].strip() or None

                if parsed.path in _OPERATIONAL_PATHS:
                    verification = params.get("verification", [""])[0].strip() or None
                    risk = params.get("risk", [""])[0].strip() or None
                    changed_only = _parse_bool(
                        params.get("changed_only", [""])[0], name="changed_only"
                    )
                    if (
                        parsed.path in {"/api/operational/graph", "/galaxy/operational"}
                        and not project_id
                    ):
                        raise ValueError("project_id is required for the operational graph")
                    operational = _operational_payload(
                        storage,
                        owner_id=owner_id,
                        project_id=project_id,
                        limit=limit,
                        verification=verification,
                        risk=risk,
                        changed_only=changed_only,
                    )
                    if parsed.path == "/galaxy/operational":
                        payload = render_galaxy_view(
                            operational,
                            project_id=project_id,
                        ).encode()
                        self._send_payload(
                            payload,
                            "text/html; charset=utf-8",
                            allow_script=True,
                        )
                    else:
                        payload = json.dumps(
                            operational,
                            ensure_ascii=False,
                            default=str,
                            indent=2,
                        ).encode()
                        self._send_payload(payload, "application/json; charset=utf-8")
                    return

                if parsed.path == "/api/maintenance/status":
                    maintenance = _maintenance_payload(
                        storage,
                        owner_id=owner_id,
                        backup_directory=backup_directory,
                        project_id=project_id,
                    )
                    payload = json.dumps(
                        maintenance,
                        ensure_ascii=False,
                        default=str,
                        indent=2,
                    ).encode()
                    self._send_payload(payload, "application/json; charset=utf-8")
                    return

                if parsed.path == "/api/table-page":
                    table = params.get("table", [""])[0].strip()
                    cursor = params.get("cursor", [""])[0].strip() or None
                    table_page = dashboard_table_page(
                        storage,
                        table=table,
                        limit=min(limit, MAX_PAGE_SIZE),
                        cursor=cursor,
                        project_id=project_id,
                        owner_id=owner_id,
                    )
                    payload = json.dumps(
                        table_page,
                        ensure_ascii=False,
                        default=str,
                        indent=2,
                    ).encode()
                    self._send_payload(payload, "application/json; charset=utf-8")
                    return

                selected_tables = _parse_tables(params.get("tables", [""])[0])
                snapshot = dashboard_snapshot(
                    storage,
                    limit=limit,
                    project_id=project_id,
                    tables=selected_tables,
                    query=query,
                )
                allow_script = False
                if parsed.path in {"/api/snapshot", "/export.json"}:
                    payload, content_type = export_snapshot(snapshot, export_format="json")
                elif parsed.path in {"/api/graph", "/api/graph/context"}:
                    graph = _build_graph(snapshot, project_id, query, limit)
                    if parsed.path == "/api/graph/context":
                        selected = [
                            item
                            for raw in params.get("select", [])
                            for item in raw.split(",")
                            if item
                        ]
                        if not selected:
                            selected = [str(node["id"]) for node in graph["nodes"][:1]]
                        graph = compact_graph_context(
                            graph,
                            selected,
                            depth=min(4, max(0, int(params.get("depth", ["1"])[0]))),
                            max_nodes=min(limit, 100),
                            max_chars=min(
                                12000,
                                max(1, int(params.get("max_chars", ["6000"])[0])),
                            ),
                        )
                    payload = json.dumps(graph, ensure_ascii=False, default=str).encode()
                    content_type = "application/json; charset=utf-8"
                elif parsed.path == "/galaxy":
                    payload = render_galaxy_view(
                        _build_graph(snapshot, project_id, query, limit),
                        project_id=project_id,
                    ).encode()
                    content_type = "text/html; charset=utf-8"
                    allow_script = True
                elif parsed.path == "/export.csv":
                    payload, content_type = export_snapshot(snapshot, export_format="csv")
                elif parsed.path in {"/", "/index.html"}:
                    try:
                        maintenance = _maintenance_payload(
                            storage,
                            owner_id=owner_id,
                            backup_directory=backup_directory,
                            project_id=project_id,
                        )
                    except DashboardStatusError as exc:
                        maintenance = {
                            "status": "error",
                            "message": str(exc),
                            "read_only": True,
                        }
                    payload = render_dashboard(snapshot, maintenance).encode()
                    content_type = "text/html; charset=utf-8"
                    allow_script = True
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
            except (ValueError, TypeError, DashboardStatusError) as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_payload(payload, content_type, allow_script=allow_script)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "status": "error",
                        "error": "invalid_content_length",
                        "message": "Content-Length must be an integer.",
                    },
                )
                return
            if content_length < 0:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "status": "error",
                        "error": "invalid_content_length",
                        "message": "Content-Length cannot be negative.",
                    },
                )
                return
            if content_length > MAX_ACTION_BODY_BYTES:
                self._send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {
                        "status": "error",
                        "error": "body_too_large",
                        "message": "Maintenance action body is too large.",
                    },
                )
                return
            body = self.rfile.read(content_length)
            status_code, result = dispatch_maintenance_action(
                storage,
                path=parsed.path,
                headers=dict(self.headers.items()),
                body=body,
                owner_id=owner_id,
                backup_directory=backup_directory,
            )
            self._send_json(status_code, result)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return DashboardHandler


def serve_dashboard(config: DashboardConfig) -> None:
    config.validate()
    storage = SQLiteStorage(config.sqlite_path)
    storage.initialize()
    server = ThreadingHTTPServer(
        (config.host, config.port),
        build_handler(
            storage,
            row_limit=config.row_limit,
            owner_id=config.owner_id,
            backup_directory=config.backup_directory,
        ),
    )
    print(f"Dashboard available at http://{config.host}:{config.port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Persistent Memory MCP dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--sqlite-path", default=str(Path.home() / ".memory-mcp" / "memory.db"))
    parser.add_argument("--row-limit", type=int, default=100)
    parser.add_argument("--owner-id", default=os.environ.get("OWNER_ID"))
    parser.add_argument(
        "--backup-dir",
        help="Optional directory containing verified backup manifests for maintenance status",
    )
    args = parser.parse_args()
    serve_dashboard(
        DashboardConfig(
            host=args.host,
            port=args.port,
            sqlite_path=Path(args.sqlite_path).expanduser().resolve(),
            row_limit=args.row_limit,
            owner_id=args.owner_id,
            backup_directory=(
                Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
            ),
        )
    )


if __name__ == "__main__":
    main()
