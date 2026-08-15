"""User-facing preview/apply command for versioned SQLite migrations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

from .migration_service import MigrationService
from .settings import RuntimeSettings


def _settings_from_env_file(path: str | Path) -> RuntimeSettings:
    """Resolve Settings from an env file with process environment taking precedence."""
    file_values = {
        str(key): str(value)
        for key, value in dotenv_values(Path(path).expanduser()).items()
        if value is not None
    }
    merged: dict[str, str] = {**file_values, **dict(os.environ)}
    return RuntimeSettings.from_env(merged)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-mcp-migrate",
        description="Preview or explicitly apply versioned local SQLite migrations.",
    )
    parser.add_argument("--env", default=".env", help="Path to the Memory MCP env file")
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Directory for the verified pre-migration backup",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply pending migrations after preview validation",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation flag when --apply is used",
    )
    return parser


def command_migrate(args: argparse.Namespace) -> int:
    settings = _settings_from_env_file(args.env)
    if settings.backend != "sqlite":
        print(
            json.dumps(
                {
                    "status": "unsupported",
                    "backend": settings.backend,
                    "message": "versioned local migrations currently apply only to SQLite",
                },
                sort_keys=True,
            )
        )
        return 2

    database = settings.sqlite_path.resolve()
    if not database.is_file():
        print(
            json.dumps(
                {
                    "status": "missing_database",
                    "message": "SQLite database does not exist; run memory-mcp init first",
                },
                sort_keys=True,
            )
        )
        return 2

    service = MigrationService(database)
    plan = service.plan()
    if not args.apply:
        print(
            json.dumps(
                {
                    "status": "preview",
                    "database": str(database),
                    "plan": plan.as_dict(),
                    "apply_command": "memory-mcp-migrate --apply --yes",
                },
                sort_keys=True,
            )
        )
        return 0

    if not args.yes:
        print(
            json.dumps(
                {
                    "status": "confirmation_required",
                    "message": "re-run with --apply --yes after reviewing the migration preview",
                    "plan": plan.as_dict(),
                },
                sort_keys=True,
            )
        )
        return 2

    backup_dir = (
        Path(args.backup_dir).expanduser().resolve()
        if args.backup_dir
        else database.parent / "backups"
    )
    result = service.apply(backup_dir)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return command_migrate(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
