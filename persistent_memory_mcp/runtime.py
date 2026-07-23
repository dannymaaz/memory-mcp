"""Package runtime entrypoint with MCP integrations installed."""

from __future__ import annotations

import argparse

from . import cli
from .code_intelligence import install_code_intelligence
from .git_verification import install_git_verification
from .security_integration import install_security_boundaries
from .server_integration import install_hybrid_search
from .session_lifecycle import install_session_lifecycle


def command_serve(_args: argparse.Namespace) -> int:
    """Run the MCP server after installing runtime integrations."""
    from src import server as server_module

    install_security_boundaries(server_module)
    install_hybrid_search(server_module)
    install_git_verification(server_module)
    install_code_intelligence(server_module)
    install_session_lifecycle(server_module)
    server_module.main()
    return 0


def main() -> None:
    """Delegate to the existing CLI with the integrated serve command."""
    cli.command_serve = command_serve
    cli.main()
