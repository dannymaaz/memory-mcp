from __future__ import annotations

from datetime import UTC, datetime

from persistent_memory_mcp.embedding_index import (
    build_embedding_update,
    embedding_is_current,
    reindex_memories,
)
from persistent_memory_mcp.hybrid_search import EmbeddingProvider, content_fingerprint, local_embedding


def test_current_embedding_is_skipped() -> None:
    item = {"id": "one", "content": "stable memory"}
    item["embedding"] = local_embedding("stable memory")
    item["embedding_fingerprint"] = content_fingerprint("stable memory")
    provider = EmbeddingProvider(max_calls=1)
    assert embedding_is_current(item, "stable memory") is True
    assert build_embedding_update(item, provider) is None
    assert provider.calls == 0


def test_stale_embedding_is_rebuilt_with_metadata() -> None:
    item = {
        "id": "one",
        "content": "new memory",
        "embedding": local_embedding("old memory"),
        "embedding_fingerprint": content_fingerprint("old memory"),
    }
    provider = EmbeddingProvider(max_calls=2)
    now = datetime(2026, 7, 22, tzinfo=UTC)
    update = build_embedding_update(item, provider, now=now)
    assert update is not None
    assert update["embedding_fingerprint"] == content_fingerprint("new memory")
    assert update["embedding_provider"] == "local"
    assert update["embedded_at"] == now.isoformat()


def test_reindex_persists_only_stale_records() -> None:
    current = {"id": "current", "content": "keep this"}
    current["embedding"] = local_embedding("keep this")
    current["embedding_fingerprint"] = content_fingerprint("keep this")
    stale = {"id": "stale", "content": "rebuild this"}
    persisted: list[dict[str, object]] = []
    metrics = reindex_memories(
        [current, stale],
        persisted.append,
        provider=EmbeddingProvider(max_calls=5),
    )
    assert metrics.scanned == 2
    assert metrics.indexed == 1
    assert metrics.skipped == 1
    assert persisted[0]["id"] == "stale"


def test_reindex_isolates_persistence_failures() -> None:
    items = [{"id": "one", "content": "first"}, {"id": "two", "content": "second"}]

    def persist(item: dict[str, object]) -> None:
        if item["id"] == "one":
            raise RuntimeError("database unavailable")

    metrics = reindex_memories(items, persist, provider=EmbeddingProvider(max_calls=5))
    assert metrics.failed == 1
    assert metrics.indexed == 1
