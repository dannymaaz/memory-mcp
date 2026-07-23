"""Package runtime entrypoint with MCP integrations installed."""

from __future__ import annotations

import argparse

from . import cli
from .server_integration import install_hybrid_search


def command_serve(_args: argparse.Namespace) -> int:
    """Run the MCP server after installing runtime integrations."""
    from src import server as server_module

    install_hybrid_search(server_module)
    server_module.main()
    return 0


def main() -> None:
    """Delegate to the existing CLI with the integrated serve command."""
    cli.command_serve = command_serve
    cli.main()
