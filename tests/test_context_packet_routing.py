from __future__ import annotations

from persistent_memory_mcp.tokenization import resolve_token_counter
from src.model_router import ModelRouter
from src.optimizer import ContextOptimizer


def test_interface_optimizer_exposes_context_packet_contract() -> None:
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_for_interface(
        {
            "project": {"id": "demo"},
            "metadata": {"recommended_model": "gpt-4.1"},
            "tasks": [{"id": "task-1", "title": "Finish Context Packet"}],
        },
        "codex",
        max_tokens=800,
        intent="finish context packet",
    )
    packet = optimized["context_packet"]
    assert packet["version"] == "1.0"
    assert packet["objective"] == "finish context packet"
    assert packet["tokens"]["budget"] == 800
    assert packet["tokens"]["count"] <= packet["tokens"]["effective_content_budget"]
    assert optimized["interface"] == "codex"
    assert optimized["strategy"]["limit"] == 800


def test_model_router_refreshes_final_packet_count_after_annotations() -> None:
    optimizer = ContextOptimizer()
    router = ModelRouter()
    optimized = optimizer.optimize_for_interface(
        {
            "project": {"id": "demo"},
            "metadata": {"recommended_model": "gpt-4.1"},
            "tasks": [{"id": "task-1", "title": "Ship safely", "priority": "high"}],
        },
        "codex",
        max_tokens=900,
    )
    routed = router.optimize_context_for_model(
        "gpt-4.1",
        optimized,
        optimizer.estimate_tokens(optimized),
    )
    tokens = routed["context_packet"]["tokens"]
    counter = resolve_token_counter(model=tokens["model"], tokenizer=tokens["tokenizer"])
    assert tokens["count"] == counter.count(routed)
    assert tokens["count"] <= tokens["budget"]
    assert routed["model"] == "gpt-4.1"
    assert routed["delivery_profile"]["style"] == "deep-reasoning"


def test_existing_256_token_context_request_remains_supported() -> None:
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_for_interface(
        {
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
        },
        "codex",
    )
    assert optimized["strategy"]["limit"] == 256
    assert optimized["context_packet"]["tokens"]["budget"] == 256
    assert optimized["context_packet"]["tokens"]["count"] <= 256
