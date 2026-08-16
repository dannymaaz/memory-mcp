from __future__ import annotations

import asyncio
from importlib.metadata import version
from types import SimpleNamespace

from mcp.server import MCPServer

from persistent_memory_mcp.tool_registry import ToolRegistry
from src import server as server_module


def _version_pair(raw: str) -> tuple[int, int]:
    parts = raw.split(".")
    return int(parts[0]), int(parts[1])


def test_installed_mcp_sdk_is_supported_v2_line() -> None:
    installed = _version_pair(version("mcp"))
    assert installed >= (2, 0)
    assert installed < (3, 0)


def test_runtime_uses_installed_mcpserver_without_local_fallback() -> None:
    assert server_module.MCPServer is MCPServer
    assert isinstance(server_module.server, MCPServer)
    assert server_module.server.__class__.__module__.startswith("mcp.server.mcpserver")


def test_tool_registry_registers_and_replaces_through_public_mcpserver_api() -> None:
    mcp_server = MCPServer(name="registry-compatibility")
    module = SimpleNamespace(server=mcp_server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])
    registry = ToolRegistry(module)

    def first(value: str) -> str:
        return f"first:{value}"

    def second(value: str) -> str:
        return f"second:{value}"

    registry.register("compatibility_sample", "Compatibility sample", first)
    registry.register("compatibility_sample", "Updated compatibility sample", second)

    tools = asyncio.run(mcp_server.list_tools())
    matching = [tool for tool in tools if tool.name == "compatibility_sample"]
    assert len(matching) == 1
    assert matching[0].description == "Updated compatibility sample"

    result = asyncio.run(
        mcp_server.call_tool("compatibility_sample", {"value": "sample"})
    )
    assert result.is_error is False
    assert any(
        getattr(content, "text", None) == "second:sample"
        for content in result.content
    )

    assert module.TOOL_HANDLERS["compatibility_sample"] is second
    assert module.TOOL_SCHEMAS == [
        {"name": "compatibility_sample", "description": "Updated compatibility sample"}
    ]


def test_packaged_runtime_keeps_stdio_entrypoint_contract(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs: object) -> None:
        calls.append(dict(kwargs))

    monkeypatch.setattr(server_module.server, "run", fake_run)
    server_module.main()

    assert calls == [{"transport": "stdio"}]