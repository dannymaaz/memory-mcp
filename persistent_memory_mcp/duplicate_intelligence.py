"""Evidence-based duplicate and contradiction analysis for memory records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .hybrid_search import cosine_similarity, local_embedding, render_memory_text

_NEGATION_RE = re.compile(
    r"\b(no|not|never|without|disabled|deny|forbid|must not)\b",
    re.IGNORECASE,
)
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

    if " ".join(left_text.split()) == " ".join(right_text.split()):
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
    candidate_id = str(candidate.get("id") or candidate.get("source_id") or "")
    for item in existing:
        item_id = str(item.get("id") or item.get("source_id") or "")
        if candidate_id and item_id == candidate_id:
            continue
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


def _replace_registered_tool(server: Any, name: str, function: Callable[..., Any]) -> None:
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        tools[name] = function
    manager = getattr(server, "_tool_manager", None)
    managed = getattr(manager, "_tools", None)
    if isinstance(managed, dict) and name in managed:
        tool = managed[name]
        if hasattr(tool, "fn"):
            tool.fn = function
        elif hasattr(tool, "function"):
            tool.function = function
        else:
            managed[name] = function


def build_relationship_tool(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Build the MCP-facing bounded relationship analysis tool."""

    def analyze_memory_relationships(
        memory_id: str,
        project_id: str | None = None,
        owner_id: str | None = None,
        *,
        limit: int = 10,
        persist: bool = False,
    ) -> dict[str, Any]:
        if not memory_id:
            return {"error": "memory_id is required", "tool": "analyze_memory_relationships"}
        if limit < 1 or limit > 100:
            return {
                "error": "limit must be between 1 and 100",
                "tool": "analyze_memory_relationships",
            }
        client = server_module._client(owner_id)
        try:
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=False,
            )
            rows = server_module._table_select(
                client,
                "memory_documents",
                {"project_id": project["id"]},
            )
            candidate = next(
                (
                    row
                    for row in rows
                    if str(row.get("id") or row.get("source_id") or "") == memory_id
                ),
                None,
            )
            if candidate is None:
                return {
                    "error": "memory record was not found in the resolved project",
                    "tool": "analyze_memory_relationships",
                }
            matches = find_memory_relationships(candidate, rows, limit=limit)
            persisted = False
            if persist:
                relationships = [
                    {
                        "memory_id": str(
                            match["item"].get("id")
                            or match["item"].get("source_id")
                            or ""
                        ),
                        "relationship": match["relationship"],
                        "recommendation": match["recommendation"],
                        "confidence": round(float(match["confidence"]), 6),
                        "evidence": match["evidence"],
                    }
                    for match in matches
                ]
                metadata = {
                    **(candidate.get("metadata") or {}),
                    "memory_relationships": relationships,
                    "memory_relationships_version": 1,
                }
                server_module._table_upsert(
                    client,
                    "memory_documents",
                    {**candidate, "metadata": metadata},
                )
                persisted = True
            return {
                "status": "ok",
                "project_id": project["id"],
                "memory_id": memory_id,
                "analyzed": max(0, len(rows) - 1),
                "matches": matches,
                "persisted": persisted,
            }
        except Exception as exc:
            return {"error": str(exc), "tool": "analyze_memory_relationships"}

    analyze_memory_relationships.__name__ = "analyze_memory_relationships"
    analyze_memory_relationships.__doc__ = (
        "Analiza duplicados, relaciones y contradicciones sin modificar contenido."
    )
    return analyze_memory_relationships


def install_duplicate_intelligence(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Install duplicate intelligence once without rewriting the legacy server."""
    if getattr(server_module, "_duplicate_intelligence_installed", False):
        return server_module.analyze_memory_relationships
    tool = build_relationship_tool(server_module)
    server_module.analyze_memory_relationships = tool
    _replace_registered_tool(server_module.server, "analyze_memory_relationships", tool)
    try:
        server_module.server.tool(
            name="analyze_memory_relationships",
            description=(
                "Analiza duplicados, relaciones y contradicciones sin modificar contenido."
            ),
        )(tool)
    except Exception:
        pass
    server_module._duplicate_intelligence_installed = True
    return tool
