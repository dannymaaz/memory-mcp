from __future__ import annotations

from importlib.metadata import version

from mcp.server.fastmcp import FastMCP

from src import server as server_module


def _version_pair(raw: str) -> tuple[int, int]:
    parts = raw.split(".")
    return int(parts[0]), int(parts[1])


def test_installed_mcp_sdk_is_supported_v1_line() -> None:
    installed = _version_pair(version("mcp"))
    assert installed >= (1, 28)
    assert installed < (2, 0)


def test_release_runtime_uses_installed_fastmcp() -> None:
    assert server_module.FastMCP is FastMCP
    assert isinstance(server_module.server, FastMCP)
    assert server_module.server.__class__.__module__.startswith("mcp.server.fastmcp")
