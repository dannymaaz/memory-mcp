from __future__ import annotations

from types import SimpleNamespace

import pytest

from persistent_memory_mcp import application as application_module
from persistent_memory_mcp.application import INITIALIZATION_ORDER, create_application
from persistent_memory_mcp.settings import RuntimeSettings


def test_create_application_preserves_initialization_order_and_is_idempotent(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[str] = []

    def recorder(name: str):
        def install(*_args, **_kwargs):
            calls.append(name)

        return install

    installer_names = {
        "install_deployment_storage": "deployment_storage",
        "install_security_boundaries": "security_boundaries",
        "install_hybrid_search": "hybrid_search",
        "install_embedding_lifecycle": "embedding_lifecycle",
        "install_duplicate_intelligence": "duplicate_intelligence",
        "install_deployment_risk": "deployment_risk",
        "install_agent_evaluation": "agent_evaluation",
        "install_confirmed_deletion": "confirmed_deletion",
        "install_verified_restore": "verified_restore",
        "install_git_verification": "git_verification",
        "install_code_intelligence": "code_intelligence",
        "install_progressive_retrieval": "progressive_retrieval",
        "install_symbol_evolution": "symbol_evolution",
        "install_paginated_reads": "paginated_reads",
        "install_continuation_contract": "continuation_contract",
        "install_session_lifecycle": "session_lifecycle",
    }
    for attribute, name in installer_names.items():
        monkeypatch.setattr(application_module, attribute, recorder(name))

    server = SimpleNamespace(_tools={}, tool=lambda **_kwargs: (lambda fn: fn))
    server_module = SimpleNamespace(server=server, main=lambda: None)
    settings = RuntimeSettings(
        backend="sqlite",
        sqlite_path=tmp_path / "memory.db",
    )

    first = create_application(settings, server_module=server_module)
    first_calls = tuple(calls)
    second = create_application(settings, server_module=server_module)

    assert first is second
    assert first_calls == INITIALIZATION_ORDER
    assert tuple(calls) == INITIALIZATION_ORDER
    assert first.settings == settings
    assert first.tool_registry.server_module is server_module


def test_create_application_rejects_recomposition_with_different_settings(
    monkeypatch,
    tmp_path,
) -> None:
    for attribute in (
        "install_deployment_storage",
        "install_security_boundaries",
        "install_hybrid_search",
        "install_embedding_lifecycle",
        "install_duplicate_intelligence",
        "install_deployment_risk",
        "install_agent_evaluation",
        "install_confirmed_deletion",
        "install_verified_restore",
        "install_git_verification",
        "install_code_intelligence",
        "install_progressive_retrieval",
        "install_symbol_evolution",
        "install_paginated_reads",
        "install_continuation_contract",
        "install_session_lifecycle",
    ):
        monkeypatch.setattr(application_module, attribute, lambda *_args, **_kwargs: None)

    server_module = SimpleNamespace(
        server=SimpleNamespace(_tools={}, tool=lambda **_kwargs: (lambda fn: fn)),
        main=lambda: None,
    )
    first_settings = RuntimeSettings(
        backend="sqlite",
        sqlite_path=tmp_path / "first.db",
    )
    second_settings = RuntimeSettings(
        backend="sqlite",
        sqlite_path=tmp_path / "second.db",
    )

    create_application(first_settings, server_module=server_module)

    with pytest.raises(RuntimeError, match="different runtime settings"):
        create_application(second_settings, server_module=server_module)
