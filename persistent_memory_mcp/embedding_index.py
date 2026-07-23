"""Deterministic embedding indexing and reindex lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, Sequence

from .hybrid_search import EmbeddingProvider, content_fingerprint, render_memory_text

PersistFunction = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ReindexMetrics:
    scanned: int
    indexed: int
    skipped: int
    failed: int
    embedding_calls: int
    fallback_used: bool
    retries: int


def embedding_is_current(item: Mapping[str, Any], text: str) -> bool:
    """Return whether a stored vector matches the current searchable content."""
    embedding = item.get("embedding")
    fingerprint = item.get("embedding_fingerprint")
    return (
        isinstance(embedding, Sequence)
        and not isinstance(embedding, (str, bytes, bytearray))
        and bool(embedding)
        and fingerprint == content_fingerprint(text)
    )


def build_embedding_update(
    item: Mapping[str, Any],
    provider: EmbeddingProvider,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Build a persistence payload for one stale or missing embedding."""
    text = render_memory_text(item)
    if not text:
        return None
    if not force and embedding_is_current(item, text):
        return None
    vector = provider.embed(text)
    timestamp = (now or datetime.now(UTC)).isoformat()
    update = dict(item)
    update["embedding"] = vector
    update["embedding_fingerprint"] = content_fingerprint(text)
    update["embedding_provider"] = provider.name
    update["embedded_at"] = timestamp
    return update


def reindex_memories(
    items: Sequence[Mapping[str, Any]],
    persist: PersistFunction,
    *,
    provider: EmbeddingProvider | None = None,
    force: bool = False,
    fail_fast: bool = False,
    now: datetime | None = None,
) -> ReindexMetrics:
    """Reindex records with bounded provider cost and per-item failure isolation."""
    embedder = provider or EmbeddingProvider()
    indexed = 0
    skipped = 0
    failed = 0
    for item in items:
        try:
            update = build_embedding_update(item, embedder, force=force, now=now)
            if update is None:
                skipped += 1
                continue
            persist(update)
            indexed += 1
        except Exception:
            failed += 1
            if fail_fast:
                raise
    return ReindexMetrics(
        scanned=len(items),
        indexed=indexed,
        skipped=skipped,
        failed=failed,
        embedding_calls=embedder.calls,
        fallback_used=embedder.fallback_used,
        retries=embedder.retries,
    )
