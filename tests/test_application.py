from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from persistent_memory_mcp import application as application_module
from persistent_memory_mcp.application import (
    APPLICATION_INTEGRATION_ORDER,
    create_application,
)
from persistent_memory_mcp.settings import RuntimeSettings


class FakeServer:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self.decorator_calls = 0

    def tool(self, *, name: str, description: str):
        assert description

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.decorator_calls += 1
            self._tools[name] = function
            return function

        return decorator


def _server_module() -> SimpleNamespace:
    return SimpleNamespace(
        server=FakeServer(),
        TOOL_HANDLERS={},
        TOOL_SCHEMAS=[],
        main=lambda: None,
    )


def test_create_application_uses_documented_integration_order(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    module = _server_module()
    settings = RuntimeSettings(sqlite_path=tmp_path / "missing.db")

    monkeypatch.setattr(
        application_module,
        "install_deployment_storage",
        lambda: calls.append("deployment_storage"),
    )

    simple = (
        "security_boundaries",
        "hybrid_search",
        "embedding_lifecycle",
        "duplicate_intelligence",
        "deployment_risk",
        "agent_evaluation",
        "git_verification",
        "code_intelligence",
        "paginated_reads",
        "continuation_contract",
        "session_lifecycle",
    )
    mapping = {
        "security_boundaries": "install_security_boundaries",
        "hybrid_search": "install_hybrid_search",
        "embedding_lifecycle": "install_embedding_lifecycle",
        "duplicate_intelligence": "install_duplicate_intelligence",
        "deployment_risk": "install_deployment_risk",
        "agent_evaluation": "install_agent_evaluation",
        "git_verification": "install_git_verification",
        "code_intelligence": "install_code_intelligence",
        "paginated_reads": "install_paginated_reads",
        "continuation_contract": "install_continuation_contract",
        "session_lifecycle": "install_session_lifecycle",
    }
    for step in simple:
        monkeypatch.setattr(
            application_module,
            mapping[step],
            lambda *_args, _step=step, **_kwargs: calls.append(_step),
        )

    monkeypatch.setattr(
        application_module,
        "install_confirmed_deletion",
        lambda *_args, **_kwargs: calls.append("confirmed_deletion"),
    )
    monkeypatch.setattr(
        application_module,
        "install_verified_restore",
        lambda *_args, **_kwargs: calls.append("verified_restore"),
    )
    monkeypatch.setattr(
        application_module,
        "install_progressive_retrieval",
        lambda *_args, **_kwargs: calls.append("progressive_retrieval"),
    )
    monkeypatch.setattr(
        application_module,
        "install_symbol_evolution",
        lambda *_args, **_kwargs: calls.append("symbol_evolution"),
    )

    app = create_application(settings, server_module=module)

    assert tuple(calls) == APPLICATION_INTEGRATION_ORDER
    assert app.installation_order == APPLICATION_INTEGRATION_ORDER
    assert app.installation_order.index("continuation_contract") < app.installation_order.index(
        "session_lifecycle"
    )
    assert app.server_module is module


def test_repeated_application_construction_does_not_duplicate_restore_or_deletion_tools(
    tmp_path,
    monkeypatch,
) -> None:
    module = _server_module()
    settings = RuntimeSettings(sqlite_path=tmp_path / "missing.db")

    monkeypatch.setattr(application_module, "install_deployment_storage", lambda: None)
    for name in (
        "install_security_boundaries",
        "install_hybrid_search",
        "install_embedding_lifecycle",
        "install_duplicate_intelligence",
        "install_deployment_risk",
        "install_agent_evaluation",
        "install_git_verification",
        "install_code_intelligence",
        "install_progressive_retrieval",
        "install_symbol_evolution",
        "install_paginated_reads",
        "install_continuation_contract",
        "install_session_lifecycle",
    ):
        monkeypatch.setattr(application_module, name, lambda *_args, **_kwargs: None)

    first = create_application(settings, server_module=module)
    second = create_application(settings, server_module=module)

    expected = {
        "plan_memory_deletion",
        "execute_memory_deletion",
        "plan_memory_restore",
        "execute_memory_restore",
    }
    assert set(module.server._tools) == expected
    assert set(module.TOOL_HANDLERS) == expected
    assert {item["name"] for item in module.TOOL_SCHEMAS} == expected
    assert len(module.TOOL_SCHEMAS) == 4
    assert module.server.decorator_calls == 4
    assert first.tool_registry is second.tool_registry


def test_application_run_starts_only_after_composition(tmp_path, monkeypatch) -> None:
    started: list[bool] = []
    module = _server_module()
    module.main = lambda: started.append(True)
    settings = RuntimeSettings(sqlite_path=tmp_path / "missing.db")

    monkeypatch.setattr(application_module, "install_deployment_storage", lambda: None)
    for name in (
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
        monkeypatch.setattr(application_module, name, lambda *_args, **_kwargs: None)

    app = create_application(settings, server_module=module)
    assert started == []
    app.run()
    assert started == [True]
