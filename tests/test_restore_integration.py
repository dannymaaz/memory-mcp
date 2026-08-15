from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from persistent_memory_mcp.restore_integration import install_verified_restore


class FakeServer:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def tool(self, *, name: str, description: str):
        assert description

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name] = function
            return function

        return decorator


def test_verified_restore_tools_register_idempotently() -> None:
    server = FakeServer()
    module = SimpleNamespace(server=server, TOOL_HANDLERS={}, TOOL_SCHEMAS=[])

    first_plan, first_execute = install_verified_restore(module)
    second_plan, second_execute = install_verified_restore(module)

    assert first_plan is second_plan
    assert first_execute is second_execute
    assert server._tools["plan_memory_restore"] is first_plan
    assert server._tools["execute_memory_restore"] is first_execute
    assert module.TOOL_HANDLERS["plan_memory_restore"] is first_plan
    assert module.TOOL_HANDLERS["execute_memory_restore"] is first_execute
    assert {item["name"] for item in module.TOOL_SCHEMAS} >= {
        "plan_memory_restore",
        "execute_memory_restore",
    }
