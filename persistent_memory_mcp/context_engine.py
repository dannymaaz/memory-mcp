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
    ),
    "detailed": (
        "project",
        "warnings",
        "tasks",
        "decisions",
        "sessions",
        "checkpoints",
        "files",
        "timeline",
    ),
}


@dataclass(frozen=True)
class ContextMetrics:
    original_tokens: int
    returned_tokens: int
    saved_tokens: int
    savings_percent: float
    selected_items: int
    dropped_items: int


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
        if metadata.get("untrusted") is True:
            return False
        if metadata.get("prompt_injection_detected") is True:
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


def _provenance(item: Mapping[str, Any]) -> Any:
    if item.get("provenance") is not None:
        return item.get("provenance")
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        return metadata.get("provenance")
    return None


def score_item(
    item: Mapping[str, Any],
    intent: str = "",
    now: datetime | None = None,
) -> float:
    """Score one memory by intent overlap, urgency, recency and status."""
    current = now or datetime.now(UTC)
    intent_terms = _terms(intent)
    item_terms = _terms(item)
    overlap = len(intent_terms & item_terms) / max(1, len(intent_terms))
    score = overlap * 6.0
    priority = str(item.get("priority", "")).lower()
    severity = str(item.get("severity", "")).lower()
    status = str(item.get("status", "")).lower()
    score += {
        "critical": 4.0,
        "high": 3.0,
        "medium": 1.5,
        "low": 0.5,
    }.get(priority, 0.0)
    score += {
        "critical": 5.0,
        "high": 3.5,
        "medium": 1.5,
        "low": 0.5,
    }.get(severity, 0.0)
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
        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for item in value:
                if isinstance(item, Mapping):
                    yield field, dict(item)


def build_context(
    context: Mapping[str, Any],
    *,
    intent: str = "",
    layer: str = "operational",
    budget: int | None = None,
    include_untrusted: bool = False,
    now: datetime | None = None,
) -> ContextResult:
    """Build compact context while preserving provenance and safety metadata."""
    normalized_layer = layer.strip().lower()
    if normalized_layer not in LAYER_FIELDS:
        raise ValueError(f"Unknown context layer: {layer}")
    token_budget = int(budget or DEFAULT_BUDGETS[normalized_layer])
    if token_budget < 128:
        raise ValueError("context budget must be at least 128 tokens")

    current = now or datetime.now(UTC)
    original_tokens = estimate_tokens(context)
    output: dict[str, Any] = {}
    if isinstance(context.get("project"), Mapping):
        output["project"] = dict(context["project"])

    candidates: list[tuple[float, str, dict[str, Any]]] = []
    seen: set[str] = set()
    dropped = 0
    for field, item in _iter_items(context, LAYER_FIELDS[normalized_layer]):
        expired = _is_expired(item, current)
        untrusted = not include_untrusted and not _is_trusted(item)
        if expired or untrusted:
            dropped += 1
            continue
        fingerprint = _fingerprint(item)
        if fingerprint in seen:
            dropped += 1
            continue
        seen.add(fingerprint)
        candidates.append((score_item(item, intent, current), field, item))

    candidates.sort(
        key=lambda entry: (
            entry[0],
            _timestamp(
                entry[2].get("updated_at") or entry[2].get("created_at")
            ),
        ),
        reverse=True,
    )

    policy = {
        "layer": normalized_layer,
        "budget": token_budget,
        "intent": intent,
        "excluded_untrusted": not include_untrusted,
    }
    selected = 0
    for score, field, item in candidates:
        annotated = dict(item)
        annotated["context_score"] = round(score, 3)
        annotated.setdefault("provenance", _provenance(item))
        trial = {
            **output,
            field: [*output.get(field, []), annotated],
            "context_policy": policy,
        }
        if estimate_tokens(trial) > token_budget:
            dropped += 1
            continue
        output[field] = [*output.get(field, []), annotated]
        selected += 1

    output["context_policy"] = policy
    metrics_placeholder = {
        "original_tokens": original_tokens,
        "returned_tokens": 0,
        "saved_tokens": 0,
        "savings_percent": 0.0,
        "selected_items": selected,
        "dropped_items": dropped,
    }
    output["context_metrics"] = metrics_placeholder

    while estimate_tokens(output) > token_budget:
        removable = [
            key
            for key in reversed(LAYER_FIELDS[normalized_layer])
            if isinstance(output.get(key), list) and output[key]
        ]
        if not removable:
            break
        output[removable[0]].pop()
        selected -= 1
        dropped += 1

    returned_tokens = estimate_tokens(output)
    saved = max(0, original_tokens - returned_tokens)
    metrics = ContextMetrics(
        original_tokens=original_tokens,
        returned_tokens=returned_tokens,
        saved_tokens=saved,
        savings_percent=(
            round((saved / original_tokens) * 100, 2)
            if original_tokens
            else 0.0
        ),
        selected_items=selected,
        dropped_items=dropped,
    )
    output["context_metrics"] = {
        "original_tokens": metrics.original_tokens,
        "returned_tokens": metrics.returned_tokens,
        "saved_tokens": metrics.saved_tokens,
        "savings_percent": metrics.savings_percent,
        "selected_items": metrics.selected_items,
        "dropped_items": metrics.dropped_items,
    }
    return ContextResult(output, metrics, normalized_layer, token_budget)
