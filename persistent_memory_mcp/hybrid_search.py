"""Provider-configurable embeddings and provider-free hybrid memory search."""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

WORD_RE = re.compile(r"[a-z0-9_./-]+", re.IGNORECASE)
EmbeddingFunction = Callable[[str], Sequence[float]]


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


def _terms(value: Any) -> list[str]:
    text = value if isinstance(value, str) else str(value)
    return [token.lower() for token in WORD_RE.findall(text) if len(token) > 1]


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
    all_terms = set(_terms(" ".join(str(item.get(key, "")) for key in (
        "title", "summary", "content", "details", "message", "file_path"
    ))))
    overlap = len(query_terms & all_terms) / len(query_terms)
    title_overlap = len(query_terms & title_terms) / len(query_terms)
    status_boost = 0.08 if str(item.get("status", "")).lower() in {
        "active", "blocked", "in_progress", "pending"
    } else 0.0
    return min(1.0, overlap * 0.75 + title_overlap * 0.25 + status_boost)


class EmbeddingProvider:
    """Resolve configured embedding providers with a safe local fallback."""

    def __init__(
        self,
        provider: str | None = None,
        external_embed: EmbeddingFunction | None = None,
        *,
        max_calls: int = 100,
    ) -> None:
        self.name = (provider or os.getenv("MEMORY_EMBEDDING_PROVIDER", "local")).strip().lower()
        self.external_embed = external_embed
        self.max_calls = max_calls
        self.calls = 0
        self.fallback_used = False

    def embed(self, text: str) -> list[float]:
        if self.calls >= self.max_calls:
            raise RuntimeError("embedding call budget exceeded")
        self.calls += 1
        if self.name == "local" or self.external_embed is None:
            self.fallback_used = self.name != "local"
            return local_embedding(text)
        try:
            return [float(value) for value in self.external_embed(text)]
        except Exception:
            self.fallback_used = True
            return local_embedding(text)


def hybrid_search(
    query: str,
    items: Sequence[Mapping[str, Any]],
    *,
    provider: EmbeddingProvider | None = None,
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
    query_vector = embedder.embed(query)
    results: list[SearchResult] = []
    denominator = lexical_weight + semantic_weight
    for raw_item in items:
        item = dict(raw_item)
        rendered = " ".join(str(item.get(key, "")) for key in (
            "title", "summary", "content", "details", "message", "file_path"
        ))
        lexical = lexical_score(query, item)
        stored = item.get("embedding")
        if isinstance(stored, Sequence) and not isinstance(stored, (str, bytes, bytearray)):
            vector = [float(value) for value in stored]
        else:
            vector = embedder.embed(rendered)
        semantic = max(0.0, cosine_similarity(query_vector, vector))
        hybrid = (lexical * lexical_weight + semantic * semantic_weight) / denominator
        if hybrid >= minimum_score:
            results.append(SearchResult(item, lexical, semantic, hybrid))
    results.sort(
        key=lambda result: (
            result.hybrid_score,
            result.lexical_score,
            str(result.item.get("updated_at") or result.item.get("created_at") or ""),
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
    )
    return selected, metrics
