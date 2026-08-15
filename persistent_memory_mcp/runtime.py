"""Package runtime entrypoint with MCP integrations installed."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from . import cli
from .code_intelligence import install_code_intelligence
from .deletion_integration import install_confirmed_deletion
from .deployment_risk import install_deployment_risk
from .deployment_storage import install_deployment_storage
from .duplicate_intelligence import install_duplicate_intelligence
from .embedding_lifecycle import install_embedding_lifecycle
from .evaluation_integration import install_agent_evaluation
from .git_verification import install_git_verification
from .migration_service import MigrationService
from .repository_retrieval import install_progressive_retrieval
from .restore_integration import install_verified_restore
from .security_integration import install_security_boundaries
from .server_integration import install_hybrid_search
from .session_lifecycle import install_session_lifecycle
from .settings import RuntimeSettings
from .symbol_evolution import install_symbol_evolution


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
    """Run the MCP server after read-only schema validation and integrations."""
    load_dotenv()
    settings = RuntimeSettings.from_env()
    _assert_migration_ready(settings)

    install_deployment_storage()
    from src import server as server_module

    install_security_boundaries(server_module)
    install_hybrid_search(server_module)
    install_embedding_lifecycle(server_module)
    install_duplicate_intelligence(server_module)
    install_deployment_risk(server_module)
    install_agent_evaluation(server_module)
    install_confirmed_deletion(server_module)
    install_verified_restore(server_module, settings)
    install_git_verification(server_module)
    install_code_intelligence(server_module)
    install_progressive_retrieval(server_module, settings)
    install_symbol_evolution(server_module, settings)
    install_session_lifecycle(server_module)
    server_module.main()
    return 0


def main() -> None:
    """Delegate to the existing CLI with the integrated serve command."""
    cli.command_serve = command_serve
    cli.main()
