"""Evidence-based duplicate and contradiction analysis for memory records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .hybrid_search import cosine_similarity, local_embedding, render_memory_text

_NEGATION_RE = re.compile(r"\b(no|not|never|without|disabled|deny|forbid|must not)\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


@dataclass(frozen=True)
class MemoryRelationship:
    """A bounded recommendation backed by lexical and semantic evidence."""

    relationship: str
    recommendation: str
    confidence: float
    lexical_score: float
    semantic_score: float
    evidence: tuple[str, ...]


def _normalized_words(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[a-z0-9_./-]+", value, flags=re.IGNORECASE)
        if len(token) > 1
    }


def _lexical_similarity(left: str, right: str) -> float:
    left_words = _normalized_words(left)
    right_words = _normalized_words(right)
    if not left_words and not right_words:
        return 1.0
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def _contradiction_signals(left: str, right: str) -> tuple[str, ...]:
    signals: list[str] = []
    left_negated = bool(_NEGATION_RE.search(left))
    right_negated = bool(_NEGATION_RE.search(right))
    if left_negated != right_negated:
        signals.append("opposing negation")

    left_numbers = set(_NUMBER_RE.findall(left))
    right_numbers = set(_NUMBER_RE.findall(right))
    if left_numbers and right_numbers and left_numbers != right_numbers:
        signals.append("different numeric thresholds")
    return tuple(signals)


def analyze_memory_relationship(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    duplicate_threshold: float = 0.88,
    related_threshold: float = 0.62,
) -> MemoryRelationship:
    """Classify two memories without deleting or mutating either record."""
    left_text = render_memory_text(left)
    right_text = render_memory_text(right)
    lexical = _lexical_similarity(left_text, right_text)
    semantic = max(
        0.0,
        cosine_similarity(local_embedding(left_text), local_embedding(right_text)),
    )
    combined = lexical * 0.45 + semantic * 0.55
    contradiction = _contradiction_signals(left_text, right_text)

    if contradiction and combined >= related_threshold:
        confidence = min(1.0, combined + 0.08 * len(contradiction))
        return MemoryRelationship(
            relationship="contradiction",
            recommendation="keep_both",
            confidence=confidence,
            lexical_score=lexical,
            semantic_score=semantic,
            evidence=contradiction,
        )

    if left_text.strip() == right_text.strip():
        return MemoryRelationship(
            relationship="exact_duplicate",
            recommendation="merge",
            confidence=1.0,
            lexical_score=1.0,
            semantic_score=1.0,
            evidence=("identical normalized content",),
        )

    if combined >= duplicate_threshold:
        return MemoryRelationship(
            relationship="semantic_duplicate",
            recommendation="merge",
            confidence=combined,
            lexical_score=lexical,
            semantic_score=semantic,
            evidence=("high lexical and semantic similarity",),
        )

    if combined >= related_threshold:
        return MemoryRelationship(
            relationship="related",
            recommendation="mark_related",
            confidence=combined,
            lexical_score=lexical,
            semantic_score=semantic,
            evidence=("shared topic or responsibility",),
        )

    return MemoryRelationship(
        relationship="distinct",
        recommendation="ignore",
        confidence=max(0.0, 1.0 - combined),
        lexical_score=lexical,
        semantic_score=semantic,
        evidence=("insufficient overlap",),
    )


def find_memory_relationships(
    candidate: Mapping[str, Any],
    existing: Sequence[Mapping[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return strongest non-distinct relationships in deterministic order."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    matches: list[dict[str, Any]] = []
    for item in existing:
        result = analyze_memory_relationship(candidate, item)
        if result.relationship == "distinct":
            continue
        matches.append(
            {
                "item": dict(item),
                "relationship": result.relationship,
                "recommendation": result.recommendation,
                "confidence": result.confidence,
                "lexical_score": result.lexical_score,
                "semantic_score": result.semantic_score,
                "evidence": list(result.evidence),
            }
        )
    matches.sort(
        key=lambda match: (
            float(match["confidence"]),
            str(match["item"].get("updated_at") or match["item"].get("created_at") or ""),
            str(match["item"].get("id") or match["item"].get("source_id") or ""),
        ),
        reverse=True,
    )
    return matches[:limit]
