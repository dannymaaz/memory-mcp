"""Local-first operational dashboard with safe read-only defaults."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from .storage import SQLiteStorage

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_DASHBOARD_TABLES = (
    "projects",
    "sessions",
    "decisions",
    "tasks",
    "warnings",
    "file_memory",
    "memory_documents",
    "retention_policies",
    "deployment_records",
)
_MAX_LIMIT = 500
_MAX_QUERY_LENGTH = 200


@dataclass(frozen=True)
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    sqlite_path: Path = Path.home() / ".memory-mcp" / "memory.db"
    row_limit: int = 100

    def validate(self) -> None:
        if self.host not in _LOOPBACK_HOSTS:
            raise ValueError("dashboard host must be localhost unless remote access is implemented")
        if not 1 <= self.port <= 65535:
            raise ValueError("dashboard port must be between 1 and 65535")
        if not 1 <= self.row_limit <= _MAX_LIMIT:
            raise ValueError(f"dashboard row_limit must be between 1 and {_MAX_LIMIT}")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (table,)
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'pragma table_info("{table}")').fetchall()}


def _order_column(columns: set[str]) -> str:
    for candidate in ("updated_at", "created_at", "started_at", "deployed_at", "id"):
        if candidate in columns:
            return candidate
    return "rowid"


def _row_matches(row: Mapping[str, Any], query: str) -> bool:
    if not query:
        return True
    serialized = json.dumps(row, ensure_ascii=False, default=str).casefold()
    return query.casefold() in serialized


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
    filtered = [row for row in decoded if _row_matches(row, query)]
    return count, filtered[:limit]


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
        "filters": {"project_id": project_id, "tables": list(selected), "query": query, "limit": limit},
        "read_only": True,
    }


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


def render_dashboard(snapshot: Mapping[str, Any]) -> str:
    """Render a dependency-free dashboard page with escaped content."""
    counts = snapshot.get("counts", {})
    tables = snapshot.get("tables", {})
    filters = snapshot.get("filters", {})
    cards = "".join(
        f"<article><strong>{html.escape(str(name))}</strong><span>{int(value)}</span></article>"
        for name, value in counts.items()
    )
    sections: list[str] = []
    for name, rows in tables.items():
        body = "".join(
            "<li><code>" + html.escape(json.dumps(row, ensure_ascii=False, default=str)) + "</code></li>"
            for row in rows
        ) or "<li>No records</li>"
        sections.append(f"<section><h2>{html.escape(str(name))}</h2><ol>{body}</ol></section>")
    query = html.escape(str(filters.get("query") or ""), quote=True)
    project = html.escape(str(filters.get("project_id") or ""), quote=True)
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Persistent Memory MCP Dashboard</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0b1220;color:#e5edf8}main{max-width:1180px;margin:auto;padding:32px}
header{margin-bottom:24px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
article,section,form{background:#121c2e;border:1px solid #26344b;border-radius:12px;padding:16px}article span{display:block;font-size:2rem;margin-top:8px}
section{margin-top:16px}ol{padding-left:20px}li{margin:8px 0;overflow-wrap:anywhere}code{white-space:pre-wrap}small{color:#9fb0c7}
form{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}input,button{padding:10px;border-radius:8px;border:1px solid #41516b;background:#0b1220;color:#e5edf8}
</style></head><body><main><header><h1>Persistent Memory MCP</h1><small>Local read-only operational dashboard</small></header>
<form method="get"><input name="project_id" placeholder="Project ID" value=""" + project + """>
<input name="q" placeholder="Search" maxlength="200" value=""" + query + ""><button type="submit">Filter</button></form>
<div class="cards">""" + cards + "</div>" + "".join(sections) + "</main></body></html>"


def _parse_tables(raw: str | None) -> tuple[str, ...] | None:
    if not raw:
        return None
    values = tuple(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    invalid = sorted(set(values) - set(_DASHBOARD_TABLES))
    if invalid:
        raise ValueError(f"unsupported dashboard table(s): {', '.join(invalid)}")
    return values


def build_handler(storage: SQLiteStorage, *, row_limit: int = 100) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def _security_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            try:
                requested = int(params.get("limit", [str(row_limit)])[0])
                limit = min(row_limit, max(1, requested))
                query = params.get("q", [""])[0].strip()
                project_id = params.get("project_id", [""])[0].strip() or None
                selected_tables = _parse_tables(params.get("tables", [""])[0])
                snapshot = dashboard_snapshot(
                    storage,
                    limit=limit,
                    project_id=project_id,
                    tables=selected_tables,
                    query=query,
                )
                if parsed.path == "/api/snapshot":
                    payload, content_type = export_snapshot(snapshot, export_format="json")
                elif parsed.path == "/export.json":
                    payload, content_type = export_snapshot(snapshot, export_format="json")
                elif parsed.path == "/export.csv":
                    payload, content_type = export_snapshot(snapshot, export_format="csv")
                elif parsed.path in {"/", "/index.html"}:
                    payload = render_dashboard(snapshot).encode()
                    content_type = "text/html; charset=utf-8"
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
            except (ValueError, TypeError) as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return DashboardHandler


def serve_dashboard(config: DashboardConfig) -> None:
    config.validate()
    storage = SQLiteStorage(config.sqlite_path)
    storage.initialize()
    server = ThreadingHTTPServer((config.host, config.port), build_handler(storage, row_limit=config.row_limit))
    print(f"Dashboard available at http://{config.host}:{config.port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Persistent Memory MCP dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--sqlite-path", default=str(Path.home() / ".memory-mcp" / "memory.db"))
    parser.add_argument("--row-limit", type=int, default=100)
    args = parser.parse_args()
    serve_dashboard(
        DashboardConfig(
            host=args.host,
            port=args.port,
            sqlite_path=Path(args.sqlite_path).expanduser().resolve(),
            row_limit=args.row_limit,
        )
    )


if __name__ == "__main__":
    main()
