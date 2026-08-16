"""Application composition root for the integrated Memory MCP runtime."""

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
from .pagination_integration import install_paginated_reads
from .repository_retrieval import install_progressive_retrieval
from .restore_integration import install_verified_restore
from .security_integration import install_security_boundaries
from .server_integration import install_hybrid_search
from .session_lifecycle import install_session_lifecycle
from .settings import RuntimeSettings
from .symbol_evolution import install_symbol_evolution
from .tool_registry import ToolRegistry

# This order is a runtime contract. In particular, Continuation must wrap
# end_session before Session Lifecycle captures it so explicit closes, handoffs,
# and idle expiry all persist the same continuation contract.
INITIALIZATION_ORDER: tuple[str, ...] = (
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

_APPLICATION_ATTR = "_persistent_memory_application"


@dataclass(frozen=True, slots=True)
class Application:
    """Fully composed runtime and the shared MCP tool registry it uses."""

    settings: RuntimeSettings
    server_module: Any
    tool_registry: ToolRegistry

    def run(self) -> None:
        """Run the already-composed MCP server."""
        self.server_module.main()


def _existing_application(
    server_module: Any,
    settings: RuntimeSettings,
) -> Application | None:
    existing = getattr(server_module, _APPLICATION_ATTR, None)
    if not isinstance(existing, Application):
        return None
    if existing.settings != settings:
        raise RuntimeError(
            "Memory MCP application is already composed with different runtime settings"
        )
    return existing


def create_application(
    settings: RuntimeSettings,
    *,
    server_module: Any | None = None,
) -> Application:
    """Compose the Memory MCP runtime once in a deterministic order.

    ``server_module`` is injectable for focused tests. Production callers omit
    it and receive the legacy ``src.server`` module behind an explicit
    application boundary.
    """
    if server_module is not None:
        existing = _existing_application(server_module, settings)
        if existing is not None:
            return existing

    # Deployment storage must be extended before importing the legacy server,
    # because that import constructs the global FastMCP server and storage path.
    install_deployment_storage()

    if server_module is None:
        from src import server as server_module

    existing = _existing_application(server_module, settings)
    if existing is not None:
        return existing

    tool_registry = ToolRegistry(server_module)

    install_security_boundaries(server_module)
    install_hybrid_search(server_module)
    install_embedding_lifecycle(server_module)
    install_duplicate_intelligence(server_module)
    install_deployment_risk(server_module)
    install_agent_evaluation(server_module)
    install_confirmed_deletion(server_module, registry=tool_registry)
    install_verified_restore(server_module, settings, registry=tool_registry)
    install_git_verification(server_module)
    install_code_intelligence(server_module)
    install_progressive_retrieval(server_module, settings)
    install_symbol_evolution(server_module, settings)
    install_paginated_reads(server_module)
    install_continuation_contract(server_module)
    install_session_lifecycle(server_module)

    application = Application(
        settings=settings,
        server_module=server_module,
        tool_registry=tool_registry,
    )
    setattr(server_module, _APPLICATION_ATTR, application)
    return application
