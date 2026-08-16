from __future__ import annotations

from importlib.metadata import version
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP

from persistent_memory_mcp.tool_registry import ToolRegistry
from src import server as server_module


def _version_pair(raw: str) -> tuple[int, int]:
    parts = raw.split(".")
    return int(parts[0]), int(parts[1])


def test_installed_mcp_sdk_is_supported_v1_line() -> None:
    installed = _version_pair(version("mcp"))
    assert installed >= (1, 28)
    assert installed < (2, 0)


def test_runtime_uses_installed_fastmcp_instead_of_local_fallback() -> None:
    assert server_module.FastMCP is FastMCP
    assert isinstance(server_module.server, FastMCP)
    assert server_module.server.__class__.__module__.startswith("mcp.server.fastmcp")


def test_tool_registry_registers_and_replaces_against_installed_fastmcp() -> None:
    mcp_server = FastMCP(name="registry-compatibility")
    module = SimpleNamespace(server=mcp_server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])
    registry = ToolRegistry(module)

    def first(value: str) -> str:
        return f"first:{value}"

    def second(value: str) -> str:
        return f"second:{value}"

    registry.register("compatibility_sample", "Compatibility sample", first)
    registry.register("compatibility_sample", "Updated compatibility sample", second)

    managed = mcp_server._tool_manager._tools["compatibility_sample"]
    assert managed.fn is second
    assert module.TOOL_HANDLERS["compatibility_sample"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "compatibility_sample", "description": "Updated compatibility sample"}
    ]
