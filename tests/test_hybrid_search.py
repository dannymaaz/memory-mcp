from __future__ import annotations

import pytest

from persistent_memory_mcp.hybrid_search import (
    EmbeddingProvider,
    cosine_similarity,
    hybrid_search,
    local_embedding,
)


def _items() -> list[dict[str, object]]:
    return [
        {
            "id": "auth",
            "title": "Fix authentication RLS",
            "content": "Resolve Supabase row level security policies.",
            "status": "blocked",
        },
        {
            "id": "docs",
            "title": "Update README",
            "content": "Document installation instructions.",
        },
        {
            "id": "deploy",
            "title": "Deploy upload notifier",
            "content": "Restart only the upload notifier service on OVH Canada.",
        },
    ]


def test_local_embedding_is_deterministic_and_private() -> None:
    first = local_embedding("authentication RLS")
    second = local_embedding("authentication RLS")
    assert first == second
    assert len(first) == 96
    assert cosine_similarity(first, second) == pytest.approx(1.0)


def test_hybrid_search_prioritizes_relevant_memory() -> None:
    results, metrics = hybrid_search(
        "fix authentication rls",
        _items(),
        limit=2,
        minimum_score=0.0,
    )
    assert results[0].item["id"] == "auth"
    assert metrics.provider == "local"
    assert metrics.returned == 2
    assert metrics.embedding_calls <= len(_items()) + 1


def test_default_minimum_score_filters_unrelated_memory() -> None:
    results, metrics = hybrid_search("fix authentication rls", _items(), limit=3)
    assert [result.item["id"] for result in results] == ["auth"]
    assert metrics.returned == 1


def test_external_provider_falls_back_without_exposing_failure() -> None:
    def failing_provider(_text: str) -> list[float]:
        raise TimeoutError("provider unavailable")

    provider = EmbeddingProvider("external", failing_provider, max_calls=10)
    results, metrics = hybrid_search("deploy notifier", _items(), provider=provider)
    assert results[0].item["id"] == "deploy"
    assert metrics.fallback_used is True


def test_stored_embeddings_avoid_candidate_embedding_calls() -> None:
    items = _items()
    for item in items:
        item["embedding"] = local_embedding(str(item["content"]))
    provider = EmbeddingProvider(max_calls=2)
    results, metrics = hybrid_search("authentication", items, provider=provider)
    assert results
    assert metrics.embedding_calls == 1


def test_call_budget_and_invalid_weights_are_enforced() -> None:
    provider = EmbeddingProvider(max_calls=1)
    with pytest.raises(RuntimeError, match="budget exceeded"):
        hybrid_search("authentication", _items(), provider=provider)
    with pytest.raises(ValueError, match="not both zero"):
        hybrid_search("authentication", _items(), lexical_weight=0, semantic_weight=0)
