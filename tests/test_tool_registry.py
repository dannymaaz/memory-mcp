from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

from persistent_memory_mcp.tool_registry import (
    ToolRegistry,
    ToolRegistryError,
    get_tool_registry,
)


class FakeTool:
    def __init__(self, function: Callable[..., Any]) -> None:
        self.fn = function


class FakeManager:
    def __init__(self) -> None:
        self._tools: dict[str, FakeTool] = {}


class FakeFastMCP:
    def __init__(self, *, use_manager: bool = False) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._tool_manager = FakeManager() if use_manager else None
        self.decorator_calls = 0

    def tool(self, *, name: str, description: str):
        assert description

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.decorator_calls += 1
            if self._tool_manager is not None:
                self._tool_manager._tools[name] = FakeTool(function)
            else:
                self._tools[name] = function
            return function

        return decorator


def _module(server: Any) -> SimpleNamespace:
    return SimpleNamespace(server=server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])


def test_register_is_idempotent_and_replaces_existing_callback() -> None:
    server = FakeFastMCP()
    module = _module(server)
    registry = ToolRegistry(module)

    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    registry.register("sample", "First description", first)
    registry.register("sample", "Updated description", second)

    assert server.decorator_calls == 1
    assert server._tools["sample"] is second
    assert module.sample is second
    assert module.TOOL_HANDLERS["sample"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "sample", "description": "Updated description"}
    ]
    assert [item.name for item in registry.registrations] == ["sample"]


def test_register_updates_fastmcp_manager_tool_without_duplicate_decorator() -> None:
    server = FakeFastMCP(use_manager=True)
    module = _module(server)
    registry = ToolRegistry(module)

    def first() -> None:
        return None

    def second() -> None:
        return None

    registry.register("managed", "Managed tool", first)
    registry.register("managed", "Managed tool", second)

    assert server.decorator_calls == 1
    assert server._tool_manager._tools["managed"].fn is second
    assert len(module.TOOL_SCHEMAS) == 1


def test_register_works_with_runtime_selected_server_class() -> None:
    from src.server import FastMCP

    server = FastMCP("registry-test")
    module = _module(server)
    registry = ToolRegistry(module)

    def first(value: str) -> str:
        return f"first:{value}"

    def second(value: str) -> str:
        return f"second:{value}"

    registry.register("runtime_sample", "Runtime server sample", first)
    registry.register("runtime_sample", "Updated runtime server sample", second)

    tools = getattr(server, "_tools", None)
    manager = getattr(server, "_tool_manager", None)
    managed = getattr(manager, "_tools", None)
    if isinstance(tools, dict):
        assert tools["runtime_sample"] is second
    elif isinstance(managed, dict):
        registered = managed["runtime_sample"]
        callback = getattr(registered, "fn", getattr(registered, "function", None))
        assert callback is second
    else:  # pragma: no cover - guards a future server implementation change
        pytest.fail("runtime-selected MCP server exposes no supported registry surface")
    assert module.TOOL_HANDLERS["runtime_sample"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "runtime_sample", "description": "Updated runtime server sample"}
    ]


def test_register_removes_legacy_duplicate_schemas() -> None:
    server = FakeFastMCP()
    module = _module(server)
    module.TOOL_SCHEMAS.extend(
        [
            {"name": "sample", "description": "old"},
            {"name": "sample", "description": "duplicate"},
        ]
    )

    def function() -> None:
        return None

    ToolRegistry(module).register("sample", "current", function)

    assert module.TOOL_SCHEMAS == [{"name": "sample", "description": "current"}]


def test_get_tool_registry_reuses_one_registry_per_module() -> None:
    module = _module(FakeFastMCP())
    assert get_tool_registry(module) is get_tool_registry(module)


def test_missing_server_registration_path_fails_clearly() -> None:
    module = SimpleNamespace(server=SimpleNamespace(), TOOL_HANDLERS={}, TOOL_SCHEMAS=[])
    registry = ToolRegistry(module)

    with pytest.raises(ToolRegistryError, match=r"tool\(\) is unavailable"):
        registry.register("required", "Required tool", lambda: None)


def test_missing_server_object_fails_clearly() -> None:
    with pytest.raises(ToolRegistryError, match="does not expose an MCP server"):
        ToolRegistry(SimpleNamespace())
