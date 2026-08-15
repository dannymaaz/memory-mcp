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
                {
                    "id": "auth",
                    "title": "Fix authentication",
                    "priority": "high",
                    "provenance": {"source": "issue", "id": "auth"},
                },
                {"id": "docs", "title": "Update docs"},
            ],
        },
        "codex",
    )
    packet = optimized["context_packet"]
    tokens = packet["tokens"]
    metrics = optimized["context_metrics"]
    assert optimized["strategy"]["limit"] == 256
    assert packet["version"] == "1.0"
    assert packet["objective"] == "fix authentication"
    assert isinstance(packet["sources"], list)
    assert packet["verification"]["status"] in {
        "verified",
        "partial",
        "unverified",
        "mixed",
        "empty",
    }
    assert tokens["budget"] == 256
    assert tokens["tokenizer"]
    assert tokens["count"] <= 256
    assert "blocks" in metrics
    for block in metrics["blocks"].values():
        assert {"selected_items", "dropped_items", "compressed_items", "tokens"} <= set(block)


def test_model_router_preserves_compact_packet_shape_and_budget() -> None:
    optimizer = ContextOptimizer()
    router = ModelRouter()
    optimized = optimizer.optimize_for_interface(
        {
            "project": {"id": "demo"},
            "metadata": {"recommended_model": "gpt-4.1"},
            "tasks": [{"id": "task-1", "title": "Ship compact packet"}],
        },
        "codex",
        max_tokens=512,
    )
    routed = router.optimize_context_for_model(
        "gpt-4.1",
        optimized,
        optimizer.estimate_tokens(optimized),
    )
    tokens = routed["context_packet"]["tokens"]
    assert "estimated_count" not in tokens
    assert tokens["count"] <= tokens["budget"] == 512
    assert routed["delivery_profile"] == {"style": "deep-reasoning"}
