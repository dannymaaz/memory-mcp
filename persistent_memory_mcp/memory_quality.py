"""Provider-free memory quality checks for duplicates and contradictions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .hybrid_search import cosine_similarity, local_embedding, render_memory_text

TOKEN_RE = re.compile(r"[a-z0-9_./-]+", re.IGNORECASE)
NEGATIONS = {"no", "not", "never", "without", "disable", "disabled", "false", "stop", "stopped"}
AFFIRMATIONS = {"yes", "enable", "enabled", "true", "allow", "allowed", "start", "started"}


@dataclass(frozen=True)
class MemoryRelation:
    left_id: str
    right_id: str
    relation: str
    score: float
    reason: str


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) > 1}


def _identity(item: Mapping[str, Any], index: int) -> str:
    return str(item.get("id") or item.get("source_id") or f"item-{index}")


def _polarity(tokens: set[str]) -> int:
    """Resolve operational polarity, giving explicit negation precedence.

    Phrases such as ``never allow`` or ``disable uploads`` contain a positive
    action word but are still unambiguously negative. Treating explicit
    negation as dominant avoids missing those contradictions while the shared
    subject and similarity checks continue to prevent broad false positives.
    """
    if tokens & NEGATIONS:
        return -1
    if tokens & AFFIRMATIONS:
        return 1
    return 0


def detect_memory_relations(
    items: Sequence[Mapping[str, Any]],
    *,
    duplicate_threshold: float = 0.86,
    contradiction_threshold: float = 0.62,
) -> list[MemoryRelation]:
    """Detect near duplicates and conservative polarity contradictions."""
    if not 0 <= contradiction_threshold <= duplicate_threshold <= 1:
        raise ValueError("thresholds must satisfy 0 <= contradiction <= duplicate <= 1")
    prepared: list[tuple[str, str, set[str], list[float]]] = []
    for index, item in enumerate(items):
        text = render_memory_text(item)
        prepared.append((_identity(item, index), text, _tokens(text), local_embedding(text)))

    relations: list[MemoryRelation] = []
    for left_index, left in enumerate(prepared):
        for right in prepared[left_index + 1 :]:
            left_id, left_text, left_tokens, left_vector = left
            right_id, right_text, right_tokens, right_vector = right
            if not left_text or not right_text:
                continue
            similarity = max(0.0, cosine_similarity(left_vector, right_vector))
            union = left_tokens | right_tokens
            lexical = len(left_tokens & right_tokens) / max(1, len(union))
            score = round((similarity * 0.65) + (lexical * 0.35), 4)
            if score >= duplicate_threshold:
                relations.append(
                    MemoryRelation(
                        left_id,
                        right_id,
                        "near_duplicate",
                        score,
                        "high semantic and lexical overlap",
                    )
                )
                continue
            left_polarity = _polarity(left_tokens)
            right_polarity = _polarity(right_tokens)
            shared_subject = left_tokens & right_tokens - NEGATIONS - AFFIRMATIONS
            if (
                score >= contradiction_threshold
                and left_polarity * right_polarity == -1
                and len(shared_subject) >= 2
            ):
                relations.append(
                    MemoryRelation(
                        left_id,
                        right_id,
                        "possible_contradiction",
                        score,
                        "shared subject with opposing polarity",
                    )
                )
    return relations
