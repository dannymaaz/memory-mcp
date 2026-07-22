"""Token-efficient, intent-aware context construction."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping, Sequence

WORD_RE = re.compile(r"[a-z0-9_./-]+", re.IGNORECASE)
DEFAULT_BUDGETS = {"short": 800, "operational": 2400, "detailed": 6000}
LAYER_FIELDS = {
    "short": ("project", "warnings", "tasks", "decisions"),
    "operational": (
        "project",
        "warnings",
        "tasks",
        "decisions",
        "sessions",
        "checkpoints",
        "files",
        "file_memory",
    ),
    "detailed": (
        "project",
        "warnings",
        "tasks",
        "decisions",
        "sessions",
        "checkpoints",
        "files",
        "file_memory",
        "timeline",
    ),
}
LONG_TEXT_FIELDS = (
    "content",
    "details",
    "summary",
    "description",
    "completed_work",
    "remaining_work",
    "next_step",
    "state",
)


@dataclass(frozen=True)
class ContextMetrics:
    original_tokens: int
    returned_tokens: int
    saved_tokens: int
    savings_percent: float
    selected_items: int
    dropped_items: int
    compressed_items: int = 0


@dataclass(frozen=True)
class ContextResult:
    context: dict[str, Any]
    metrics: ContextMetrics
    layer: str
    budget: int


def estimate_tokens(payload: Any) -> int:
    """Estimate tokens without requiring a provider tokenizer."""
    if isinstance(payload, str):
        serialized = payload
    else:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return max(1, math.ceil(len(serialized) / 4))


def _terms(value: Any) -> set[str]:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, default=str)
    return {token.lower() for token in WORD_RE.findall(value) if len(token) > 1}


def _timestamp(value: Any) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _is_expired(item: Mapping[str, Any], now: datetime) -> bool:
    value = item.get("expires_at")
    if not value:
        return False
    try:
        expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry <= now
    except ValueError:
        return True


def _is_trusted(item: Mapping[str, Any]) -> bool:
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        if metadata.get("untrusted") is True or metadata.get("prompt_injection_detected") is True:
            return False
    return item.get("trusted", True) is not False


def _fingerprint(item: Mapping[str, Any]) -> str:
    for key in ("id", "source_id"):
        if item.get(key):
            return f"{key}:{item[key]}"
    text = " ".join(
        str(item.get(key, ""))
        for key in ("title", "summary", "content", "message", "file_path")
    )
    return "text:" + " ".join(sorted(_terms(text)))


def _compact_text(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    boundary = normalized.rfind(". ", 0, max_chars)
    cutoff = boundary + 1 if boundary >= max_chars // 2 else max_chars
    return normalized[:cutoff].rstrip(" ,;:") + "…"


def compress_memory_item(
    item: Mapping[str, Any],
    *,
    item_type: str = "memory",
    max_tokens: int = 180,
) -> dict[str, Any]:
    """Compress oversized session/checkpoint data while preserving key metadata."""
    if max_tokens < 48:
        raise ValueError("item compression budget must be at least 48 tokens")
    compact = dict(item)
    original_tokens = estimate_tokens(compact)
    if original_tokens <= max_tokens:
        return compact

    max_chars = max_tokens * 3
    protected = {
        "id",
        "project_id",
        "owner_id",
        "title",
        "status",
        "priority",
        "severity",
        "interface",
        "created_at",
        "updated_at",
        "expires_at",
        "provenance",
    }
    result = {
        key: value
        for key, value in compact.items()
        if key in protected and value not in (None, "", [], {})
    }
    text_budget = max(80, max_chars - len(json.dumps(result, default=str)))
    text_fields = [key for key in LONG_TEXT_FIELDS if compact.get(key) not in (None, "", [], {})]
    per_field = max(60, text_budget // max(1, len(text_fields)))
    for key in text_fields:
        value = compact[key]
        rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        result[key] = _compact_text(rendered, per_field)

    metadata = compact.get("metadata")
    if isinstance(metadata, Mapping):
        safe_metadata = {
            key: metadata[key]
            for key in ("provenance", "current_goal", "next_step", "repo", "source")
            if key in metadata
        }
        if safe_metadata:
            result["metadata"] = safe_metadata
    result["compression"] = {
        "type": item_type,
        "original_tokens": original_tokens,
        "compressed_tokens": estimate_tokens(result),
        "strategy": "deterministic-extractive",
    }
    return result


def score_item(item: Mapping[str, Any], intent: str = "", now: datetime | None = None) -> float:
    """Score one memory by intent overlap, urgency, recency and status."""
    current = now or datetime.now(UTC)
    intent_terms = _terms(intent)
    item_terms = _terms(item)
    overlap = len(intent_terms & item_terms) / max(1, len(intent_terms))
    score = overlap * 6.0
    priority = str(item.get("priority", "")).lower()
    severity = str(item.get("severity", "")).lower()
    status = str(item.get("status", "")).lower()
    score += {"critical": 4.0, "high": 3.0, "medium": 1.5, "low": 0.5}.get(priority, 0.0)
    score += {"critical": 5.0, "high": 3.5, "medium": 1.5, "low": 0.5}.get(severity, 0.0)
    if status in {"active", "in_progress", "blocked", "pending"}:
        score += 1.5
    created = _timestamp(item.get("updated_at") or item.get("created_at"))
    if created:
        age_days = max(0.0, (current.timestamp() - created) / 86400)
        score += max(0.0, 2.0 - min(2.0, age_days / 30))
    return score


def _iter_items(
    context: Mapping[str, Any],
    fields: Iterable[str],
) -> Iterable[tuple[str, dict[str, Any]]]:
    for field in fields:
        value = context.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                if isinstance(item, Mapping):
                    yield field, dict(item)


def _render_selected(
    project: dict[str, Any] | None,
    selected: Sequence[tuple[str, dict[str, Any]]],
    policy: Mapping[str, Any],
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if project is not None:
        output["project"] = dict(project)
    for field, item in selected:
        output.setdefault(field, []).append(dict(item))
    output["context_policy"] = dict(policy)
    if metrics is not None:
        output["context_metrics"] = dict(metrics)
    return output


def build_context(
    context: Mapping[str, Any],
    *,
    intent: str = "",
    layer: str = "operational",
    budget: int | None = None,
    include_untrusted: bool = False,
    compress_oversized: bool = True,
    item_budget: int = 180,
    now: datetime | None = None,
) -> ContextResult:
    """Build compact context while enforcing the final serialized token budget."""
    normalized_layer = layer.strip().lower()
    if normalized_layer not in LAYER_FIELDS:
        raise ValueError(f"Unknown context layer: {layer}")
    token_budget = int(budget or DEFAULT_BUDGETS[normalized_layer])
    if token_budget < 128:
        raise ValueError("context budget must be at least 128 tokens")

    current = now or datetime.now(UTC)
    original_tokens = estimate_tokens(context)
    project = dict(context["project"]) if isinstance(context.get("project"), Mapping) else None
    policy = {
        "layer": normalized_layer,
        "budget": token_budget,
        "intent": intent,
        "excluded_untrusted": not include_untrusted,
        "compression": "deterministic-extractive" if compress_oversized else "disabled",
        "item_budget": item_budget,
    }

    candidates: list[tuple[float, str, dict[str, Any]]] = []
    seen: set[str] = set()
    dropped = 0
    compressed = 0
    for field, item in _iter_items(context, LAYER_FIELDS[normalized_layer]):
        if _is_expired(item, current) or (not include_untrusted and not _is_trusted(item)):
            dropped += 1
            continue
        fingerprint = _fingerprint(item)
        if fingerprint in seen:
            dropped += 1
            continue
        seen.add(fingerprint)
        if (
            compress_oversized
            and field in {"sessions", "checkpoints"}
            and estimate_tokens(item) > item_budget
        ):
            item = compress_memory_item(item, item_type=field.rstrip("s"), max_tokens=item_budget)
            compressed += 1
        candidates.append((score_item(item, intent, current), field, item))

    candidates.sort(
        key=lambda entry: (
            entry[0],
            _timestamp(entry[2].get("updated_at") or entry[2].get("created_at")),
        ),
        reverse=True,
    )

    selected: list[tuple[str, dict[str, Any]]] = []
    placeholder_metrics = {
        "original_tokens": original_tokens,
        "returned_tokens": token_budget,
        "saved_tokens": max(0, original_tokens - token_budget),
        "savings_percent": 0.0,
        "selected_items": len(candidates),
        "dropped_items": dropped,
        "compressed_items": compressed,
    }
    for score, field, item in candidates:
        annotated = dict(item)
        annotated["context_score"] = round(score, 3)
        metadata = item.get("metadata")
        metadata_provenance = metadata.get("provenance") if isinstance(metadata, Mapping) else None
        annotated.setdefault("provenance", item.get("provenance") or metadata_provenance)
        trial = _render_selected(
            project,
            [*selected, (field, annotated)],
            policy,
            placeholder_metrics,
        )
        if estimate_tokens(trial) > token_budget:
            dropped += 1
            continue
        selected.append((field, annotated))

    while True:
        provisional = _render_selected(project, selected, policy)
        returned_tokens = estimate_tokens(provisional)
        saved = max(0, original_tokens - returned_tokens)
        metrics_data = {
            "original_tokens": original_tokens,
            "returned_tokens": returned_tokens,
            "saved_tokens": saved,
            "savings_percent": round((saved / original_tokens) * 100, 2)
            if original_tokens
            else 0.0,
            "selected_items": len(selected),
            "dropped_items": dropped,
            "compressed_items": compressed,
        }
        output = _render_selected(project, selected, policy, metrics_data)
        final_tokens = estimate_tokens(output)
        if final_tokens <= token_budget or not selected:
            metrics_data["returned_tokens"] = final_tokens
            metrics_data["saved_tokens"] = max(0, original_tokens - final_tokens)
            metrics_data["savings_percent"] = (
                round((metrics_data["saved_tokens"] / original_tokens) * 100, 2)
                if original_tokens
                else 0.0
            )
            output["context_metrics"] = metrics_data
            break
        selected.pop()
        dropped += 1

    final_tokens = estimate_tokens(output)
    metrics = ContextMetrics(
        original_tokens=original_tokens,
        returned_tokens=final_tokens,
        saved_tokens=max(0, original_tokens - final_tokens),
        savings_percent=(
            round((max(0, original_tokens - final_tokens) / original_tokens) * 100, 2)
            if original_tokens
            else 0.0
        ),
        selected_items=len(selected),
        dropped_items=dropped,
        compressed_items=compressed,
    )
    output["context_metrics"] = {
        "original_tokens": metrics.original_tokens,
        "returned_tokens": metrics.returned_tokens,
        "saved_tokens": metrics.saved_tokens,
        "savings_percent": metrics.savings_percent,
        "selected_items": metrics.selected_items,
        "dropped_items": metrics.dropped_items,
        "compressed_items": metrics.compressed_items,
    }
    return ContextResult(output, metrics, normalized_layer, token_budget)
