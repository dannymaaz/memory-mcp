"""Package runtime entrypoint with MCP integrations installed."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from . import cli
from .application import create_application
from .migration_service import MigrationService
from .settings import RuntimeSettings


def _assert_migration_ready(settings: RuntimeSettings) -> None:
    """Read migration state and refuse to serve an existing stale SQLite schema."""
    if settings.backend != "sqlite":
        return

    database = settings.sqlite_path.resolve()
    if not database.is_file():
        return

    plan = MigrationService(database).plan()
    if not plan.pending:
        return

    pending = ", ".join(
        f"{int(item['version']):04d}_{item['name']}" for item in plan.pending
    )
    raise RuntimeError(
        "SQLite database has pending migrations "
        f"({pending}). The MCP server will not mutate the database automatically. "
        "Review the upgrade with `memory-mcp-migrate` and apply it explicitly with "
        "`memory-mcp-migrate --apply --yes`, then start the server again."
    )


def command_serve(_args: argparse.Namespace) -> int:
    """Validate schema, compose the application, and run the MCP server."""
    load_dotenv()
    settings = RuntimeSettings.from_env()
    _assert_migration_ready(settings)

    application = create_application(settings)
    application.run()
    return 0


def main() -> None:
    """Delegate to the existing CLI with the integrated serve command."""
    cli.command_serve = command_serve
    cli.main()
