"""Tests for context optimization utilities."""

from __future__ import annotations

from src.optimizer import ContextOptimizer


def test_estimate_tokens_for_string() -> None:
    optimizer = ContextOptimizer()
    assert optimizer.estimate_tokens("abcd" * 10) == 10


def test_estimate_tokens_for_dict() -> None:
    optimizer = ContextOptimizer()
    tokens = optimizer.estimate_tokens({"message": "hello", "count": 2})
    assert tokens >= 1


def test_trim_context_reduces_lists() -> None:
    optimizer = ContextOptimizer()
    context = {
        "project": {"id": "demo"},
        "decisions": [{"summary": "a" * 300} for _ in range(4)],
        "tasks": [{"title": "b" * 300} for _ in range(4)],
        "warnings": [{"message": "c" * 300} for _ in range(4)],
        "sessions": [{"interface": "native", "summary": "d" * 1000} for _ in range(4)],
    }
    trimmed = optimizer.trim_context(context, 180)
    assert optimizer.estimate_tokens(trimmed) <= 180
    assert len(trimmed.get("sessions", [])) <= len(context["sessions"])


def test_trim_context_handles_empty_lists() -> None:
    optimizer = ContextOptimizer()
    context = {"project": {"id": "demo"}, "decisions": [], "tasks": []}
    assert optimizer.trim_context(context, 128)["project"]["id"] == "demo"


def test_optimize_for_interface_sets_metadata() -> None:
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_for_interface({"project": {}}, "qwen-code")
    assert optimized["interface"] == "qwen-code"
    assert optimized["strategy"]["limit"] == 32000
    assert optimized["token_estimate"] >= 1


def test_context_request_exposes_intent_layer_and_budget() -> None:
    optimizer = ContextOptimizer()
    context = {
        "project": {"id": "demo"},
        "context_request": {
            "intent": "fix authentication",
            "layer": "short",
            "budget": 256,
        },
        "tasks": [
            {"id": "auth", "title": "Fix authentication", "priority": "high"},
            {"id": "docs", "title": "Update docs"},
        ],
    }
    optimized = optimizer.optimize_for_interface(context, "codex")
    assert optimized["strategy"]["intent"] == "fix authentication"
    assert optimized["strategy"]["layer"] == "short"
    assert optimized["strategy"]["limit"] == 256
    assert optimized["tasks"][0]["id"] == "auth"


def test_environment_defaults_are_supported(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_CONTEXT_LAYER", "short")
    monkeypatch.setenv("MEMORY_CONTEXT_BUDGET", "256")
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_for_interface({"project": {}}, "native")
    assert optimized["strategy"]["layer"] == "short"
    assert optimized["strategy"]["limit"] == 256


def test_project_guardrails_are_always_loaded_compactly() -> None:
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_for_interface(
        {
            "project": {"id": "demo"},
            "project_guardrails": {
                "project": {
                    "project_id": "demo",
                    "repository": "dannymaaz/demo",
                },
                "critical_rules": ["Never deploy the wrong service"],
                "services": [
                    {
                        "service_id": "bot-a",
                        "deployment_target": "vps-a",
                        "restart_command": "systemctl restart bot-a",
                    }
                ],
                "credential_references": [
                    {
                        "type": "ssh",
                        "path_variable": "SSH_KEY_PATH",
                        "private_key": "secret-value",
                    }
                ],
            },
        },
        "codex",
        layer="short",
        max_tokens=800,
    )
    guardrails = optimized["project"]["guardrails"]
    assert optimized["strategy"]["guardrails_loaded"] is True
    assert guardrails["services"][0]["service_id"] == "bot-a"
    assert "private_key" not in guardrails["credential_references"][0]
