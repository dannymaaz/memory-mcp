from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

from persistent_memory_mcp.tool_registry import ToolRegistry


class ManagedTool:
    def __init__(self, function: Callable[..., Any]) -> None:
        self.fn = function


class FakeServer:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._tool_manager = SimpleNamespace(_tools={})
        self.decorator_calls = 0

    def tool(self, *, name: str, description: str):
        assert description

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.decorator_calls += 1
            self._tool_manager._tools[name] = ManagedTool(function)
            return function

        return decorator


def test_register_is_idempotent_and_replaces_existing_callable() -> None:
    server = FakeServer()
    module = SimpleNamespace(server=server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])
    registry = ToolRegistry(module)

    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    registry.register("example", "First description", first)
    registry.register("example", "Updated description", second)

    assert server.decorator_calls == 1
    assert server._tool_manager._tools["example"].fn is second
    assert module.example is second
    assert module.TOOL_HANDLERS["example"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "example", "description": "Updated description"}
    ]


def test_existing_fallback_registry_is_replaced_without_reregistering() -> None:
    called = False

    def should_not_register(**_kwargs: Any):
        nonlocal called
        called = True
        raise AssertionError("existing tool should be replaced in place")

    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    server = SimpleNamespace(_tools={"example": first}, tool=should_not_register)
    module = SimpleNamespace(server=server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])
    ToolRegistry(module).register("example", "Example", second)

    assert called is False
    assert server._tools["example"] is second
    assert module.TOOL_HANDLERS["example"] is second


def test_registration_failure_is_not_silently_ignored() -> None:
    def broken_tool(**_kwargs: Any):
        def decorator(_function: Callable[..., Any]) -> Callable[..., Any]:
            raise ValueError("registration failed")

        return decorator

    module = SimpleNamespace(
        server=SimpleNamespace(tool=broken_tool),
        TOOL_HANDLERS={},
        TOOL_SCHEMAS=[],
    )

    with pytest.raises(RuntimeError, match="failed to register MCP tool 'example'"):
        ToolRegistry(module).register("example", "Example", lambda: None)

    assert "example" not in module.TOOL_HANDLERS
    assert module.TOOL_SCHEMAS == []
