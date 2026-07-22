from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENV_KEYS = ("SUPABASE_URL", "SUPABASE_KEY", "OWNER_ID")


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
    path.write_text(
        "# Persistent Memory MCP configuration\n"
        f"SUPABASE_URL={values['SUPABASE_URL']}\n"
        f"SUPABASE_KEY={values['SUPABASE_KEY']}\n"
        f"OWNER_ID={values['OWNER_ID']}\n"
        "# Optional direct PostgreSQL connection\n"
        f"DATABASE_URL={values.get('DATABASE_URL', '')}\n",
        encoding="utf-8",
    )


def _config_block(values: dict[str, str]) -> dict[str, object]:
    return {
        "mcpServers": {
            "persistent-memory-mcp": {
                "command": "memory-mcp",
                "env": {key: values[key] for key in ENV_KEYS},
            }
        }
    }


def _check_supabase(url: str, key: str) -> tuple[bool, str]:
    if not url.startswith("https://") or not key:
        return False, "Supabase URL or key is missing"
    request = Request(f"{url.rstrip('/')}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urlopen(request, timeout=8) as response:  # nosec B310 - user supplied HTTPS endpoint
            return response.status < 500, f"HTTP {response.status}"
    except HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except (URLError, TimeoutError) as exc:
        return False, str(exc)


def command_init(args: argparse.Namespace) -> int:
    env_path = Path(args.env).expanduser().resolve()
    current = _read_env(env_path)
    url = args.supabase_url or current.get("SUPABASE_URL") or input("Supabase URL: ").strip()
    key = args.supabase_key or current.get("SUPABASE_KEY") or input("Supabase anon key: ").strip()
    owner = args.owner_id or current.get("OWNER_ID") or f"owner-{secrets.token_hex(6)}"
    values = {"SUPABASE_URL": url, "SUPABASE_KEY": key, "OWNER_ID": owner, "DATABASE_URL": current.get("DATABASE_URL", "")}
    _write_env(env_path, values)
    config_path = Path(args.config).expanduser().resolve()
    config_path.write_text(json.dumps(_config_block(values), indent=2) + "\n", encoding="utf-8")
    ok, detail = _check_supabase(url, key) if not args.skip_connection_test else (True, "skipped")
    print(f"✓ Environment written to {env_path}")
    print(f"✓ MCP config written to {config_path}")
    print(f"{'✓' if ok else '!' } Supabase connection: {detail}")
    print("Next: run schema.sql in Supabase, then add the generated config to your MCP client.")
    return 0 if ok else 1


def command_doctor(args: argparse.Namespace) -> int:
    env_path = Path(args.env).expanduser().resolve()
    values = {**_read_env(env_path), **{key: os.getenv(key, "") for key in ENV_KEYS if os.getenv(key)}}
    failures = 0
    print("Persistent Memory MCP doctor")
    print(f"{'✓' if sys.version_info >= (3, 10) else '✗'} Python {sys.version.split()[0]}")
    for key in ENV_KEYS:
        present = bool(values.get(key))
        print(f"{'✓' if present else '✗'} {key}")
        failures += int(not present)
    if values.get("SUPABASE_URL") and values.get("SUPABASE_KEY"):
        ok, detail = _check_supabase(values["SUPABASE_URL"], values["SUPABASE_KEY"])
        print(f"{'✓' if ok else '✗'} Supabase API ({detail})")
        failures += int(not ok)
    print(f"{'✓' if Path('schema.sql').exists() else '!'} schema.sql available")
    return 1 if failures else 0


def command_status(args: argparse.Namespace) -> int:
    values = {**_read_env(Path(args.env).expanduser()), **{key: os.getenv(key, "") for key in ENV_KEYS if os.getenv(key)}}
    print(json.dumps({"package": "persistent-memory-mcp", "configured": all(values.get(k) for k in ENV_KEYS), "owner_id": values.get("OWNER_ID", ""), "backend": "supabase"}, indent=2))
    return 0


def command_serve(_args: argparse.Namespace) -> int:
    from src.server import main as server_main

    server_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-mcp", description="Persistent project memory for MCP-compatible AI agents")
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="Create .env and MCP client configuration")
    init.add_argument("--env", default=".env")
    init.add_argument("--config", default="persistent-memory-mcp.json")
    init.add_argument("--supabase-url")
    init.add_argument("--supabase-key")
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
