from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client_installer import (
    detect_config_path,
    install_client_config,
    installation_manifest,
    list_backups,
    rollback_config,
    uninstall_client_config,
)
from .storage import SQLiteStorage, normalize_backend

CLIENTS = ("codex", "claude", "opencode", "antigravity")
CLIENT_LABELS = {
    "codex": "OpenAI Codex",
    "claude": "Claude Code",
    "opencode": "OpenCode",
    "antigravity": "Google Antigravity",
}
BACKENDS = ("sqlite", "supabase", "postgresql")
ENV_KEYS = (
    "MEMORY_BACKEND",
    "OWNER_ID",
    "SQLITE_PATH",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
)


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
    lines = ["# Persistent Memory MCP configuration"]
    lines.extend(f"{key}={values.get(key, '')}" for key in ENV_KEYS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_values(env: str | Path) -> dict[str, str]:
    values = _read_env(Path(env).expanduser())
    values.update({key: value for key in ENV_KEYS if (value := os.getenv(key))})
    return values


def _runtime_env(values: dict[str, str]) -> dict[str, str]:
    backend = normalize_backend(values.get("MEMORY_BACKEND"))
    keys = ["MEMORY_BACKEND", "OWNER_ID"]
    if backend == "sqlite":
        keys.append("SQLITE_PATH")
    elif backend == "supabase":
        keys.extend(["SUPABASE_URL", "SUPABASE_KEY"])
    else:
        keys.append("DATABASE_URL")
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
        print("! Enter client numbers from 1 to 5, names, or 'all'.")


def _prompt_backend(current: str | None = None) -> str:
    default = normalize_backend(current or "sqlite")
    for index, backend in enumerate(BACKENDS, start=1):
        print(f"  {index}. {backend}{' [default]' if backend == default else ''}")
    answer = input(f"Backend [{BACKENDS.index(default) + 1}]: ").strip()
    if not answer:
        return default
    if answer.isdigit() and 1 <= int(answer) <= len(BACKENDS):
        return BACKENDS[int(answer) - 1]
    return normalize_backend(answer)


def _confirm(prompt: str, *, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes", "s", "si", "sí"}


def _codex_toml(values: dict[str, str]) -> str:
    env_items = ", ".join(
        f'{json.dumps(key)} = {json.dumps(value)}' for key, value in _runtime_env(values).items()
    )
    return (
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
        payload = {"type": "stdio", "command": "memory-mcp", "args": [], "env": _runtime_env(values)}
        return "claude-server.json", json.dumps(payload, indent=2) + "\n"
    if client == "opencode":
        return "opencode.json", json.dumps(_opencode_config(values), indent=2) + "\n"
    if client == "antigravity":
        return "antigravity-mcp_config.json", json.dumps(_config_block(values), indent=2) + "\n"
    raise ValueError(f"Unsupported client: {client}")


def _install_payload(client: str, values: dict[str, str]) -> dict[str, object] | str:
    if client == "codex":
        return _codex_toml(values)
    if client == "claude":
        return {"type": "stdio", "command": "memory-mcp", "args": [], "env": _runtime_env(values)}
    if client == "opencode":
        return _opencode_config(values)["mcp"]["persistent-memory-mcp"]  # type: ignore[index]
    if client == "antigravity":
        return _server_config(values)
    raise ValueError(f"Unsupported client: {client}")


def _write_client_configs(output_dir: Path, clients: list[str], values: dict[str, str]) -> dict[str, Path]:
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
        with urlopen(request, timeout=8) as response:  # nosec B310
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
        configured = bool(values.get("DATABASE_URL"))
        return configured, "DATABASE_URL configured" if configured else "DATABASE_URL missing"
    if skip_remote:
        return True, "skipped"
    return _check_supabase(values.get("SUPABASE_URL", ""), values.get("SUPABASE_KEY", ""))


def _selected_clients(args: argparse.Namespace) -> list[str]:
    clients = _normalize_clients(getattr(args, "clients", None))
    return clients or (_prompt_clients() if sys.stdin.isatty() else list(CLIENTS))


def command_init(args: argparse.Namespace) -> int:
    env_path = Path(args.env).expanduser().resolve()
    current = _read_env(env_path)
    try:
        backend = normalize_backend(args.backend) if args.backend else (
            _prompt_backend(current.get("MEMORY_BACKEND"))
            if sys.stdin.isatty()
            else normalize_backend(current.get("MEMORY_BACKEND") or "sqlite")
        )
        clients = _selected_clients(args)
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
    written = _write_client_configs(Path(args.output_dir).expanduser().resolve(), clients, values)
    ok, detail = _check_backend(values, skip_remote=args.skip_connection_test)
    print(f"✓ Environment written to {env_path}")
    for client, path in written.items():
        print(f"✓ {CLIENT_LABELS[client]} configuration written to {path}")
    if getattr(args, "install", False):
        if _confirm("Install into the selected client configuration files?", assume_yes=args.yes):
            for client in clients:
                result = install_client_config(client, _install_payload(client, values))
                print(f"{'✓' if result.changed else '='} {client}: {result.config_path}")
        else:
            print("! Automatic installation skipped; generated snippets remain available.")
    print(f"{'✓' if ok else '✗'} {backend} backend: {detail}")
    return 0 if ok else 1


def command_install(args: argparse.Namespace) -> int:
    values = _load_values(args.env)
    try:
        normalize_backend(values.get("MEMORY_BACKEND"))
        clients = _selected_clients(args)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 2
    if not _confirm("Modify the selected client configuration files?", assume_yes=args.yes):
        print("Installation cancelled.")
        return 1
    for client in clients:
        override = Path(args.config_path).expanduser() if args.config_path and len(clients) == 1 else None
        result = install_client_config(client, _install_payload(client, values), config_path=override)
        print(f"{'✓ installed' if result.changed else '= already configured'} {client}: {result.config_path}")
        if result.backup_path:
            print(f"  backup: {result.backup_path}")
    return 0


def command_uninstall(args: argparse.Namespace) -> int:
    try:
        clients = _selected_clients(args)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 2
    if not _confirm("Remove Persistent Memory MCP from selected clients?", assume_yes=args.yes):
        print("Uninstall cancelled.")
        return 1
    for client in clients:
        override = Path(args.config_path).expanduser() if args.config_path and len(clients) == 1 else None
        result = uninstall_client_config(client, config_path=override)
        print(f"{'✓ removed' if result.changed else '= not installed'} {client}: {result.config_path}")
    return 0


def command_backups(args: argparse.Namespace) -> int:
    clients = _selected_clients(args)
    rows = []
    for client in clients:
        path = detect_config_path(client)
        rows.append({"client": client, "config_path": str(path), "backups": [str(p) for p in list_backups(path)]})
    print(json.dumps({"manifest": installation_manifest(), "clients": rows}, indent=2, default=str))
    return 0


def command_rollback(args: argparse.Namespace) -> int:
    client = args.client.strip().lower()
    config = Path(args.config_path).expanduser() if args.config_path else detect_config_path(client)
    backups = list_backups(config)
    backup = Path(args.backup).expanduser() if args.backup else (backups[0] if backups else None)
    if backup is None:
        print(f"✗ No backup found for {client}")
        return 1
    if not _confirm(f"Restore {backup} to {config}?", assume_yes=args.yes):
        print("Rollback cancelled.")
        return 1
    rollback_config(config, backup)
    print(f"✓ Restored {config} from {backup}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    values = _load_values(args.env)
    failures = int(sys.version_info < (3, 11))
    print("Persistent Memory MCP doctor")
    print(f"{'✓' if not failures else '✗'} Python {sys.version.split()[0]}")
    try:
        backend = normalize_backend(values.get("MEMORY_BACKEND"))
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    owner_present = bool(values.get("OWNER_ID"))
    print(f"{'✓' if owner_present else '✗'} OWNER_ID")
    failures += int(not owner_present)
    ok, detail = _check_backend(values)
    print(f"{'✓' if ok else '✗'} {backend} backend ({detail})")
    return 1 if failures or not ok else 0


def command_status(args: argparse.Namespace) -> int:
    values = _load_values(args.env)
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
        "installations": installation_manifest().get("installations", {}),
    }, indent=2))
    return 0


def command_serve(_args: argparse.Namespace) -> int:
    from src.server import main as server_main
    server_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-mcp", description="Persistent project memory for MCP-compatible AI agents")
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="Configure storage and MCP clients")
    init.add_argument("--env", default=".env")
    init.add_argument("--output-dir", default="persistent-memory-mcp-config")
    init.add_argument("--clients")
    init.add_argument("--backend", choices=BACKENDS)
    init.add_argument("--sqlite-path")
    init.add_argument("--supabase-url")
    init.add_argument("--supabase-key")
    init.add_argument("--database-url")
    init.add_argument("--owner-id")
    init.add_argument("--skip-connection-test", action="store_true")
    init.add_argument("--install", action="store_true", help="Install into real client configs")
    init.add_argument("--yes", action="store_true", help="Confirm configuration writes")
    init.set_defaults(func=command_init)
    install = sub.add_parser("install", help="Safely install into client configuration files")
    install.add_argument("--env", default=".env")
    install.add_argument("--clients", default="all")
    install.add_argument("--config-path")
    install.add_argument("--yes", action="store_true")
    install.set_defaults(func=command_install)
    uninstall = sub.add_parser("uninstall", help="Remove only the managed MCP entry")
    uninstall.add_argument("--clients", default="all")
    uninstall.add_argument("--config-path")
    uninstall.add_argument("--yes", action="store_true")
    uninstall.set_defaults(func=command_uninstall)
    backups = sub.add_parser("backups", help="List installation manifest and backups")
    backups.add_argument("--clients", default="all")
    backups.set_defaults(func=command_backups)
    rollback = sub.add_parser("rollback", help="Restore a selected or latest backup")
    rollback.add_argument("client", choices=CLIENTS)
    rollback.add_argument("--backup")
    rollback.add_argument("--config-path")
    rollback.add_argument("--yes", action="store_true")
    rollback.set_defaults(func=command_rollback)
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
