from __future__ import annotations

from types import SimpleNamespace

from persistent_memory_mcp.evaluation_integration import install_agent_evaluation


def _server_module() -> SimpleNamespace:
    return SimpleNamespace(server=SimpleNamespace(tool=lambda **kwargs: (lambda fn: fn)))


def test_evaluation_tool_runs_bounded_suite() -> None:
    tool = install_agent_evaluation(_server_module())
    result = tool(
        [
            {
                "name": "select project",
                "category": "targeting",
                "expected": "memory-mcp",
                "observed": "Memory-MCP",
                "source": "git:remote",
                "verification_state": "verified",
            },
            {
                "name": "avoid duplicate",
                "category": "duplicate_avoidance",
                "expected": True,
                "observed": True,
            },
        ],
        baseline_tokens=1000,
        actual_tokens=500,
    )
    assert result["status"] == "ok"
    assert result["evaluation"]["overall_score"] == 1.0
    assert result["evaluation"]["token_efficiency"]["qualified"] is True


def test_evaluation_tool_rejects_unknown_category() -> None:
    tool = install_agent_evaluation(_server_module())
    result = tool(
        [{"name": "unsafe", "category": "execute_code", "expected": 1, "observed": 1}]
    )
    assert "unsupported evaluation category" in result["error"]


def test_evaluation_tool_requires_token_pair() -> None:
    tool = install_agent_evaluation(_server_module())
    result = tool(
        [{"name": "handoff", "category": "handoff", "expected": "ok", "observed": "ok"}],
        baseline_tokens=100,
    )
    assert result["error"] == "baseline_tokens and actual_tokens must be provided together"


def test_install_is_idempotent() -> None:
    module = _server_module()
    first = install_agent_evaluation(module)
    second = install_agent_evaluation(module)
    assert first is second
