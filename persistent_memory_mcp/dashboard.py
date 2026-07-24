"""Local-first operational dashboard with safe read-only defaults."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
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
    "deployment_records",
)


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
        if not 1 <= self.row_limit <= 500:
            raise ValueError("dashboard row_limit must be between 1 and 500")


def dashboard_snapshot(storage: SQLiteStorage, *, limit: int = 100) -> dict[str, Any]:
    """Return a bounded, read-only operational snapshot."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    tables: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for table in _DASHBOARD_TABLES:
        if table not in storage.allowed_tables:
            tables[table] = []
            counts[table] = 0
            continue
        try:
            rows = storage.select(table)
        except Exception:
            rows = []
        rows = sorted(
            rows,
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )
        counts[table] = len(rows)
        tables[table] = rows[:limit]
    return {
        "backend": storage.backend_name,
        "database": str(storage.path),
        "counts": counts,
        "tables": tables,
        "read_only": True,
    }


def render_dashboard(snapshot: Mapping[str, Any]) -> str:
    """Render a dependency-free dashboard page with escaped content."""
    counts = snapshot.get("counts", {})
    tables = snapshot.get("tables", {})
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
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Persistent Memory MCP Dashboard</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0b1220;color:#e5edf8}main{max-width:1180px;margin:auto;padding:32px}
header{margin-bottom:24px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
article,section{background:#121c2e;border:1px solid #26344b;border-radius:12px;padding:16px}article span{display:block;font-size:2rem;margin-top:8px}
section{margin-top:16px}ol{padding-left:20px}li{margin:8px 0;overflow-wrap:anywhere}code{white-space:pre-wrap}small{color:#9fb0c7}
</style></head><body><main><header><h1>Persistent Memory MCP</h1><small>Local read-only operational dashboard</small></header>
<div class="cards">""" + cards + "</div>" + "".join(sections) + "</main></body></html>"


def build_handler(storage: SQLiteStorage, *, row_limit: int = 100) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            requested = params.get("limit", [str(row_limit)])[0]
            try:
                limit = min(row_limit, max(1, int(requested)))
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "invalid limit")
                return
            snapshot = dashboard_snapshot(storage, limit=limit)
            if parsed.path == "/api/snapshot":
                payload = json.dumps(snapshot, ensure_ascii=False, default=str).encode()
                content_type = "application/json; charset=utf-8"
            elif parsed.path in {"/", "/index.html"}:
                payload = render_dashboard(snapshot).encode()
                content_type = "text/html; charset=utf-8"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
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
