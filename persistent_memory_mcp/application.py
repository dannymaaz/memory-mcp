"""Explicit application composition root for the integrated MCP runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .code_intelligence import install_code_intelligence
from .continuation_contract import install_continuation_contract
from .deletion_integration import install_confirmed_deletion
from .deployment_risk import install_deployment_risk
from .deployment_storage import install_deployment_storage
from .duplicate_intelligence import install_duplicate_intelligence
from .embedding_lifecycle import install_embedding_lifecycle
from .evaluation_integration import install_agent_evaluation
from .git_verification import install_git_verification
from .migration_service import MigrationService
from .pagination_integration import install_paginated_reads
from .repository_retrieval import install_progressive_retrieval
from .restore_integration import install_verified_restore
from .security_integration import install_security_boundaries
from .server_integration import install_hybrid_search
from .session_lifecycle import install_session_lifecycle
from .settings import RuntimeSettings
from .symbol_evolution import install_symbol_evolution
from .tool_registry import ToolRegistry, get_tool_registry

APPLICATION_INTEGRATION_ORDER = (
    "deployment_storage",
    "security_boundaries",
    "hybrid_search",
    "embedding_lifecycle",
    "duplicate_intelligence",
    "deployment_risk",
    "agent_evaluation",
    "confirmed_deletion",
    "verified_restore",
    "git_verification",
    "code_intelligence",
    "progressive_retrieval",
    "symbol_evolution",
    "paginated_reads",
    "continuation_contract",
    "session_lifecycle",
)


@dataclass(frozen=True)
class Application:
    """One composed MCP application without starting its transport."""

    settings: RuntimeSettings
    server_module: Any
    tool_registry: ToolRegistry
    installation_order: tuple[str, ...] = APPLICATION_INTEGRATION_ORDER

    def run(self) -> None:
        """Start the already-composed server transport."""
        self.server_module.main()


def assert_migration_ready(settings: RuntimeSettings) -> None:
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


def create_application(
    settings: RuntimeSettings,
    *,
    server_module: Any | None = None,
) -> Application:
    """Compose the MCP application deterministically without starting stdio transport."""
    assert_migration_ready(settings)

    # Storage extensions must exist before src.server creates its first local client.
    install_deployment_storage()
    if server_module is None:
        from src import server as active_server_module
    else:
        active_server_module = server_module

    registry = get_tool_registry(active_server_module)

    install_security_boundaries(active_server_module)
    install_hybrid_search(active_server_module)
    install_embedding_lifecycle(active_server_module)
    install_duplicate_intelligence(active_server_module)
    install_deployment_risk(active_server_module)
    install_agent_evaluation(active_server_module)
    install_confirmed_deletion(active_server_module, registry=registry)
    install_verified_restore(active_server_module, settings, registry=registry)
    install_git_verification(active_server_module)
    install_code_intelligence(active_server_module)
    install_progressive_retrieval(active_server_module, settings)
    install_symbol_evolution(active_server_module, settings)
    install_paginated_reads(active_server_module)
    # Continuation must wrap end_session before Session Lifecycle captures it.
    # That makes explicit close, handoff and idle expiry persist the same contract.
    install_continuation_contract(active_server_module)
    install_session_lifecycle(active_server_module)

    return Application(
        settings=settings,
        server_module=active_server_module,
        tool_registry=registry,
    )
