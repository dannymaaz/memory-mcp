from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from persistent_memory_mcp.restore_integration import install_verified_restore


class FakeServer:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def add_tool(
        self,
        function: Callable[..., Any],
        *,
        name: str,
        description: str,
    ) -> None:
        assert description
        self.tools[name] = function

    def remove_tool(self, name: str) -> None:
        del self.tools[name]


def test_verified_restore_tools_register_idempotently() -> None:
    server = FakeServer()
    module = SimpleNamespace(server=server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])

    first_plan, first_execute = install_verified_restore(module)
    second_plan, second_execute = install_verified_restore(module)

    assert first_plan is second_plan
    assert first_execute is second_execute
    assert server.tools["plan_memory_restore"] is first_plan
    assert server.tools["execute_memory_restore"] is first_execute
    assert module.TOOL_HANDLERS["plan_memory_restore"] is first_plan
    assert module.TOOL_HANDLERS["execute_memory_restore"] is first_execute
    assert {item["name"] for item in module.TOOL_SCHEMAS} >= {
        "plan_memory_restore",
        "execute_memory_restore",
    }