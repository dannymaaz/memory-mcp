from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

from persistent_memory_mcp.tool_registry import ToolRegistry


class FakeServer:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}
        self.add_calls = 0
        self.remove_calls = 0

    def add_tool(
        self,
        function: Callable[..., Any],
        *,
        name: str,
        description: str,
    ) -> None:
        assert description
        self.add_calls += 1
        self.tools[name] = function

    def remove_tool(self, name: str) -> None:
        self.remove_calls += 1
        del self.tools[name]


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

    assert server.add_calls == 2
    assert server.remove_calls == 1
    assert server.tools["example"] is second
    assert module.example is second
    assert module.TOOL_HANDLERS["example"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "example", "description": "Updated description"}
    ]


def test_known_tool_uses_public_remove_then_add() -> None:
    server = FakeServer()

    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    server.tools["example"] = first
    module = SimpleNamespace(
        server=server,
        TOOL_HANDLERS={"example": first},
        TOOL_SCHEMAS=[{"name": "example", "description": "Old"}],
    )
    ToolRegistry(module).register("example", "Example", second)

    assert server.remove_calls == 1
    assert server.add_calls == 1
    assert server.tools["example"] is second
    assert module.TOOL_HANDLERS["example"] is second
    assert module.TOOL_SCHEMAS == [{"name": "example", "description": "Example"}]


def test_registration_failure_is_not_silently_ignored() -> None:
    def broken_add_tool(
        _function: Callable[..., Any],
        *,
        name: str,
        description: str,
    ) -> None:
        del name, description
        raise ValueError("registration failed")

    module = SimpleNamespace(
        server=SimpleNamespace(add_tool=broken_add_tool),
        TOOL_HANDLERS={},
        TOOL_SCHEMAS=[],
    )

    with pytest.raises(RuntimeError, match="failed to register MCP tool 'example'"):
        ToolRegistry(module).register("example", "Example", lambda: None)

    assert "example" not in module.TOOL_HANDLERS
    assert module.TOOL_SCHEMAS == []


def test_missing_public_add_tool_is_explicit() -> None:
    module = SimpleNamespace(server=SimpleNamespace(), TOOL_HANDLERS={}, TOOL_SCHEMAS=[])

    with pytest.raises(RuntimeError, match="MCPServer.add_tool API is unavailable"):
        ToolRegistry(module).register("example", "Example", lambda: None)