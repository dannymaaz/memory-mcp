"""Package runtime entrypoint with the composed MCP application."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from . import cli
from .application import assert_migration_ready, create_application
from .settings import RuntimeSettings

# Backward-compatible private alias retained for existing tests/importers while
# the guard itself now belongs to the explicit application composition layer.
_assert_migration_ready = assert_migration_ready


def command_serve(_args: argparse.Namespace) -> int:
    """Build the validated MCP application and run its transport."""
    load_dotenv()
    settings = RuntimeSettings.from_env()
    application = create_application(settings)
    application.run()
    return 0


def main() -> None:
    """Delegate to the existing CLI with the integrated serve command."""
    cli.command_serve = command_serve
    cli.main()
