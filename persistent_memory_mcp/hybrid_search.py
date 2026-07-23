"""Provider-configurable embeddings and provider-free hybrid memory search."""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

WORD_RE = re.compile(r"[a-z0-9_./-]+", re.IGNORECASE)
EmbeddingFunction = Callable[[str], Sequence[float]]
SleepFunction = Callable[[float], None]


@dataclass(frozen=True)
class SearchResult:
    item: dict[str, Any]
    lexical_score: float
    semantic_score: float
    hybrid_score: float


@dataclass(frozen=True)
class SearchMetrics:
    provider: str
    candidates: int
    returned: int
    embedding_calls: int
    fallback_used: bool
    retries: int = 0


def _terms(value: Any) -> list[str]:
    text = value if isinstance(value, str) else str(value)
    return [token.lower() for token in WORD_RE.findall(text) if len(token) > 1]


def render_memory_text(item: Mapping[str, Any]) -> str:
    """Render stable searchable text from a memory record."""
    return " ".join(
        str(item.get(key, ""))
        for key in ("title", "summary", "content", "details", "message", "file_path")
    ).strip()


def content_fingerprint(text: str) -> str:
    """Return a stable digest used to detect stale persisted embeddings."""
    normalized = " ".join(str(text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def local_embedding(text: str, dimensions: int = 96) -> list[float]:
    """Build a deterministic private embedding without network access."""
    if dimensions < 16:
        raise ValueError("embedding dimensions must be at least 16")
    vector = [0.0] * dimensions
    for token in _terms(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = -1.0 if digest[4] & 1 else 1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity while rejecting incompatible vectors."""
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def lexical_score(query: str, item: Mapping[str, Any]) -> float:
    """Score exact term overlap with small title and status boosts."""
    query_terms = set(_terms(query))
    if not query_terms:
        return 0.0
    title_terms = set(_terms(item.get("title") or item.get("summary") or ""))
    all_terms = set(_terms(render_memory_text(item)))
    overlap = len(query_terms & all_terms) / len(query_terms)
    title_overlap = len(query_terms & title_terms) / len(query_terms)
    status_boost = 0.08 if str(item.get("status", "")).lower() in {
        "active",
        "blocked",
        "in_progress",
        "pending",
    } else 0.0
    return min(1.0, overlap * 0.75 + title_overlap * 0.25 + status_boost)


class EmbeddingProvider:
    """Resolve configured embedding providers with bounded retries and local fallback."""

    def __init__(
        self,
        provider: str | None = None,
        external_embed: EmbeddingFunction | None = None,
        *,
        max_calls: int = 100,
        max_retries: int = 2,
        retry_base_seconds: float = 0.25,
        sleep: SleepFunction = time.sleep,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if retry_base_seconds < 0:
            raise ValueError("retry_base_seconds must be non-negative")
        self.name = (provider or os.getenv("MEMORY_EMBEDDING_PROVIDER", "local")).strip().lower()
        self.external_embed = external_embed
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self.sleep = sleep
        self.calls = 0
        self.retries = 0
        self.fallback_used = False

    def _consume_call(self) -> None:
        if self.calls >= self.max_calls:
            raise RuntimeError("embedding call budget exceeded")
        self.calls += 1

    def embed(self, text: str) -> list[float]:
        if self.name == "local" or self.external_embed is None:
            self._consume_call()
            self.fallback_used = self.name != "local"
            return local_embedding(text)

        for attempt in range(self.max_retries + 1):
            self._consume_call()
            try:
                vector = [float(value) for value in self.external_embed(text)]
                if not vector or any(not math.isfinite(value) for value in vector):
                    raise ValueError("embedding provider returned an invalid vector")
                return vector
            except Exception:
                if attempt >= self.max_retries:
                    self.fallback_used = True
                    return local_embedding(text)
                self.retries += 1
                self.sleep(self.retry_base_seconds * (2**attempt))
        raise AssertionError("unreachable")


def hybrid_search(
    query: str,
    items: Sequence[Mapping[str, Any]],
    *,
    provider: EmbeddingProvider | None = None,
    query_embedding: Sequence[float] | None = None,
    limit: int = 10,
    lexical_weight: float = 0.45,
    semantic_weight: float = 0.55,
    minimum_score: float = 0.05,
) -> tuple[list[SearchResult], SearchMetrics]:
    """Rank memories using lexical and semantic evidence with bounded cost."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if lexical_weight < 0 or semantic_weight < 0 or lexical_weight + semantic_weight <= 0:
        raise ValueError("search weights must be non-negative and not both zero")
    embedder = provider or EmbeddingProvider()
    query_vector = (
        [float(value) for value in query_embedding]
        if query_embedding is not None
        else embedder.embed(query)
    )
    results: list[SearchResult] = []
    denominator = lexical_weight + semantic_weight
    for raw_item in items:
        item = dict(raw_item)
        rendered = render_memory_text(item)
        lexical = lexical_score(query, item)
        stored = item.get("embedding")
        if isinstance(stored, Sequence) and not isinstance(stored, (str, bytes, bytearray)):
            vector = [float(value) for value in stored]
        else:
            vector = embedder.embed(rendered)
        try:
            semantic = max(0.0, cosine_similarity(query_vector, vector))
        except ValueError:
            semantic = 0.0
        hybrid = (lexical * lexical_weight + semantic * semantic_weight) / denominator
        if hybrid >= minimum_score:
            results.append(SearchResult(item, lexical, semantic, hybrid))
    results.sort(
        key=lambda result: (
            result.hybrid_score,
            result.lexical_score,
            str(result.item.get("updated_at") or result.item.get("created_at") or ""),
            str(result.item.get("id") or result.item.get("source_id") or ""),
        ),
        reverse=True,
    )
    selected = results[:limit]
    metrics = SearchMetrics(
        provider=embedder.name,
        candidates=len(items),
        returned=len(selected),
        embedding_calls=embedder.calls,
        fallback_used=embedder.fallback_used,
        retries=embedder.retries,
    )
    return selected, metrics
