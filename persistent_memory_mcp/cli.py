from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .storage import SQLiteStorage, normalize_backend

CLIENTS = ("codex", "claude", "opencode", "antigravity")
CLIENT_LABELS = {
    "codex": "OpenAI Codex",
    "claude": "Claude Code",
    "opencode": "OpenCode",
    "antigravity": "Google Antigravity",
}
BACKENDS = ("sqlite", "supabase", "postgresql")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = (
        "MEMORY_BACKEND",
        "OWNER_ID",
        "SQLITE_PATH",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "DATABASE_URL",
    )
    lines = ["# Persistent Memory MCP configuration"]
    lines.extend(f"{key}={values.get(key, '')}" for key in ordered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _runtime_env(values: dict[str, str]) -> dict[str, str]:
    backend = normalize_backend(values.get("MEMORY_BACKEND"))
    keys = ["MEMORY_BACKEND", "OWNER_ID"]
    if backend == "sqlite":
        keys.append("SQLITE_PATH")
    elif backend == "supabase":
        keys.extend(["SUPABASE_URL", "SUPABASE_KEY"])
    else:
        keys.extend(["DATABASE_URL", "SUPABASE_URL", "SUPABASE_KEY"])
    return {key: values.get(key, "") for key in keys if values.get(key, "")}


def _server_config(values: dict[str, str]) -> dict[str, object]:
    return {"command": "memory-mcp", "env": _runtime_env(values)}


def _config_block(values: dict[str, str]) -> dict[str, object]:
    return {"mcpServers": {"persistent-memory-mcp": _server_config(values)}}


def _normalize_clients(raw: str | None) -> list[str]:
    if not raw:
        return []
    tokens = [token.strip().lower() for token in raw.split(",") if token.strip()]
    if "all" in tokens:
        return list(CLIENTS)
    invalid = sorted(set(tokens) - set(CLIENTS))
    if invalid:
        raise ValueError(
            f"Unknown client(s): {', '.join(invalid)}. Choose from: {', '.join(CLIENTS)}, all"
        )
    return list(dict.fromkeys(tokens))


def _prompt_clients() -> list[str]:
    print("\nWhere do you want to use Persistent Memory MCP?")
    for index, client in enumerate(CLIENTS, start=1):
        print(f"  {index}. {CLIENT_LABELS[client]}")
    print("  5. All clients")
    while True:
        answer = input("Clients [5]: ").strip() or "5"
        if answer.lower() == "all" or "5" in {item.strip() for item in answer.split(",")}:
            return list(CLIENTS)
        try:
            indexes = [int(item.strip()) for item in answer.split(",")]
        except ValueError:
            try:
                return _normalize_clients(answer)
            except ValueError as exc:
                print(f"! {exc}")
                continue
        if all(1 <= index <= len(CLIENTS) for index in indexes):
            return list(dict.fromkeys(CLIENTS[index - 1] for index in indexes))
        print("! Enter client numbers from 1 to 5, names separated by commas, or 'all'.")


def _prompt_backend(current: str | None = None) -> str:
    default = normalize_backend(current or "sqlite")
    labels = {
        "sqlite": "SQLite local (recommended for individual/offline use)",
        "supabase": "Supabase cloud",
        "postgresql": "Direct PostgreSQL",
    }
    print("\nWhere should Persistent Memory MCP store knowledge?")
    for index, backend in enumerate(BACKENDS, start=1):
        suffix = " [default]" if backend == default else ""
        print(f"  {index}. {labels[backend]}{suffix}")
    answer = input(f"Backend [{BACKENDS.index(default) + 1}]: ").strip()
    if not answer:
        return default
    if answer.isdigit() and 1 <= int(answer) <= len(BACKENDS):
        return BACKENDS[int(answer) - 1]
    return normalize_backend(answer)


def _codex_toml(values: dict[str, str]) -> str:
    env_items = ", ".join(
        f'{json.dumps(key)} = {json.dumps(value)}' for key, value in _runtime_env(values).items()
    )
    return (
        "# Merge this block into ~/.codex/config.toml\n"
        "[mcp_servers.persistent-memory-mcp]\n"
        'command = "memory-mcp"\n'
        f"env = {{ {env_items} }}\n"
    )


def _opencode_config(values: dict[str, str]) -> dict[str, object]:
    return {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "persistent-memory-mcp": {
                "type": "local",
                "command": ["memory-mcp"],
                "environment": _runtime_env(values),
                "enabled": True,
            }
        },
    }


def _client_payload(client: str, values: dict[str, str]) -> tuple[str, str]:
    if client == "codex":
        return "codex-config.toml", _codex_toml(values)
    if client == "claude":
        payload = {
            "type": "stdio",
            "command": "memory-mcp",
            "args": [],
            "env": _runtime_env(values),
        }
        return "claude-server.json", json.dumps(payload, indent=2) + "\n"
    if client == "opencode":
        return "opencode.json", json.dumps(_opencode_config(values), indent=2) + "\n"
    if client == "antigravity":
        return "antigravity-mcp_config.json", json.dumps(_config_block(values), indent=2) + "\n"
    raise ValueError(f"Unsupported client: {client}")


def _write_client_configs(
    output_dir: Path, clients: list[str], values: dict[str, str]
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for client in clients:
        filename, content = _client_payload(client, values)
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        written[client] = path
    return written


def _check_supabase(url: str, key: str) -> tuple[bool, str]:
    if not url.startswith("https://") or not key:
        return False, "Supabase URL or key is missing"
    request = Request(
        f"{url.rstrip('/')}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urlopen(request, timeout=8) as response:  # nosec B310 - HTTPS supplied by user
            return response.status < 500, f"HTTP {response.status}"
    except HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except (URLError, TimeoutError) as exc:
        return False, str(exc)


def _check_backend(values: dict[str, str], skip_remote: bool = False) -> tuple[bool, str]:
    backend = normalize_backend(values.get("MEMORY_BACKEND"))
    if backend == "sqlite":
        storage = SQLiteStorage(values["SQLITE_PATH"])
        storage.initialize()
        return storage.healthcheck()
    if backend == "postgresql":
        return (bool(values.get("DATABASE_URL")), "DATABASE_URL configured" if values.get("DATABASE_URL") else "DATABASE_URL missing")
    if skip_remote:
        return True, "skipped"
    return _check_supabase(values.get("SUPABASE_URL", ""), values.get("SUPABASE_KEY", ""))


def command_init(args: argparse.Namespace) -> int:
    env_path = Path(args.env).expanduser().resolve()
    current = _read_env(env_path)
    try:
        backend = normalize_backend(args.backend) if args.backend else (
            _prompt_backend(current.get("MEMORY_BACKEND")) if sys.stdin.isatty() else normalize_backend(current.get("MEMORY_BACKEND") or "sqlite")
        )
    except ValueError as exc:
        print(f"✗ {exc}")
        return 2

    owner = args.owner_id or current.get("OWNER_ID") or f"owner-{secrets.token_hex(6)}"
    sqlite_default = current.get("SQLITE_PATH") or str(Path.home() / ".memory-mcp" / "memory.db")
    values = {
        "MEMORY_BACKEND": backend,
        "OWNER_ID": owner,
        "SQLITE_PATH": str(Path(args.sqlite_path or sqlite_default).expanduser().resolve()),
        "SUPABASE_URL": args.supabase_url or current.get("SUPABASE_URL", ""),
        "SUPABASE_KEY": args.supabase_key or current.get("SUPABASE_KEY", ""),
        "DATABASE_URL": args.database_url or current.get("DATABASE_URL", ""),
    }
    if backend == "supabase" and sys.stdin.isatty():
        values["SUPABASE_URL"] = values["SUPABASE_URL"] or input("Supabase URL: ").strip()
        values["SUPABASE_KEY"] = values["SUPABASE_KEY"] or input("Supabase anon key: ").strip()
    if backend == "postgresql" and sys.stdin.isatty():
        values["DATABASE_URL"] = values["DATABASE_URL"] or input("PostgreSQL DATABASE_URL: ").strip()

    _write_env(env_path, values)
    try:
        clients = _normalize_clients(args.clients)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 2
    if not clients:
        clients = _prompt_clients() if sys.stdin.isatty() else list(CLIENTS)

    output_dir = Path(args.output_dir).expanduser().resolve()
    written = _write_client_configs(output_dir, clients, values)
    ok, detail = _check_backend(values, skip_remote=args.skip_connection_test)
    print(f"✓ Environment written to {env_path}")
    for client, path in written.items():
        print(f"✓ {CLIENT_LABELS[client]} configuration written to {path}")
    print(f"{'✓' if ok else '✗'} {backend} backend: {detail}")
    if backend == "sqlite":
        print("Next: run memory-mcp serve. The local database is initialized automatically.")
    else:
        print("Next: apply schema.sql to the remote database, then run memory-mcp serve.")
    return 0 if ok else 1


def command_doctor(args: argparse.Namespace) -> int:
    env_path = Path(args.env).expanduser().resolve()
    values = {**_read_env(env_path), **{key: value for key in (
        "MEMORY_BACKEND", "OWNER_ID", "SQLITE_PATH", "SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL"
    ) if (value := os.getenv(key))}}
    failures = 0
    print("Persistent Memory MCP doctor")
    print(f"{'✓' if sys.version_info >= (3, 11) else '✗'} Python {sys.version.split()[0]}")
    failures += int(sys.version_info < (3, 11))
    try:
        backend = normalize_backend(values.get("MEMORY_BACKEND"))
        print(f"✓ MEMORY_BACKEND={backend}")
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    owner_present = bool(values.get("OWNER_ID"))
    print(f"{'✓' if owner_present else '✗'} OWNER_ID")
    failures += int(not owner_present)
    ok, detail = _check_backend(values)
    print(f"{'✓' if ok else '✗'} {backend} backend ({detail})")
    failures += int(not ok)
    return 1 if failures else 0


def command_status(args: argparse.Namespace) -> int:
    values = {**_read_env(Path(args.env).expanduser()), **{key: value for key in (
        "MEMORY_BACKEND", "OWNER_ID", "SQLITE_PATH", "SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL"
    ) if (value := os.getenv(key))}}
    try:
        backend = normalize_backend(values.get("MEMORY_BACKEND"))
    except ValueError:
        backend = "invalid"
    configured = bool(values.get("OWNER_ID")) and (
        bool(values.get("SQLITE_PATH")) if backend == "sqlite" else
        bool(values.get("SUPABASE_URL") and values.get("SUPABASE_KEY")) if backend == "supabase" else
        bool(values.get("DATABASE_URL"))
    )
    print(json.dumps({
        "package": "persistent-memory-mcp",
        "configured": configured,
        "owner_id": values.get("OWNER_ID", ""),
        "backend": backend,
        "sqlite_path": values.get("SQLITE_PATH", "") if backend == "sqlite" else "",
        "supported_clients": list(CLIENTS),
    }, indent=2))
    return 0


def command_serve(_args: argparse.Namespace) -> int:
    from src.server import main as server_main

    server_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-mcp",
        description="Persistent project memory for MCP-compatible AI agents",
    )
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="Configure storage and MCP clients")
    init.add_argument("--env", default=".env")
    init.add_argument("--output-dir", default="persistent-memory-mcp-config")
    init.add_argument("--clients", help="codex,claude,opencode,antigravity, or all")
    init.add_argument("--backend", choices=BACKENDS)
    init.add_argument("--sqlite-path")
    init.add_argument("--supabase-url")
    init.add_argument("--supabase-key")
    init.add_argument("--database-url")
    init.add_argument("--owner-id")
    init.add_argument("--skip-connection-test", action="store_true")
    init.set_defaults(func=command_init)
    doctor = sub.add_parser("doctor", help="Diagnose configuration and connectivity")
    doctor.add_argument("--env", default=".env")
    doctor.set_defaults(func=command_doctor)
    status = sub.add_parser("status", help="Show a safe configuration summary")
    status.add_argument("--env", default=".env")
    status.set_defaults(func=command_status)
    serve = sub.add_parser("serve", help="Run the MCP server over stdio")
    serve.set_defaults(func=command_serve)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        args = parser.parse_args(["serve"])
    raise SystemExit(args.func(args))
