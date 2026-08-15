"""Versioned Context Packet compiler built on the existing context engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from persistent_memory_mcp.context_engine import (
    DEFAULT_BUDGETS,
    LAYER_FIELDS,
    ContextResult,
    build_context,
)
from persistent_memory_mcp.tokenization import TokenCounter, measure_tokens, resolve_token_counter

CONTEXT_PACKET_VERSION = "1.0"
DEFAULT_SAFETY_MARGIN = 0.08
MIN_CONTEXT_PACKET_BUDGET = 320
_REMOVABLE_FIELDS = (
    "timeline",
    "sessions",
    "checkpoints",
    "file_memory",
    "files",
    "decisions",
    "tasks",
    "warnings",
)
_SOURCE_KEYS = ("source", "path", "file_path", "repo", "commit", "ref", "url", "id")


@dataclass(frozen=True)
class ContextPacketResult:
    """Compiled packet plus the legacy context result used as its ranked source."""

    context: dict[str, Any]
    legacy_result: ContextResult
    counter: TokenCounter
    budget: int
    effective_budget: int

    @property
    def packet(self) -> dict[str, Any]:
        value = self.context.get("context_packet")
        return dict(value) if isinstance(value, Mapping) else {}


def _compact(value: Any, max_chars: int = 180) -> str:
    rendered = value if isinstance(value, str) else str(value)
    normalized = " ".join(rendered.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip(" ,;:") + "…"


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _provenance(item: Mapping[str, Any]) -> Any:
    if item.get("provenance") not in (None, "", [], {}):
        return item.get("provenance")
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        return metadata.get("provenance")
    return None


def _source_label(item: Mapping[str, Any]) -> str | None:
    provenance = _provenance(item)
    if provenance in (None, "", [], {}):
        return None
    if isinstance(provenance, str):
        return _compact(provenance, 160)
    if isinstance(provenance, Mapping):
        parts = [
            f"{key}={_compact(provenance[key], 100)}"
            for key in _SOURCE_KEYS
            if provenance.get(key) not in (None, "", [], {})
        ]
        return " | ".join(parts[:4]) if parts else "structured-provenance"
    return _compact(provenance, 160)


def _selected_content_items(payload: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    items: list[tuple[str, dict[str, Any]]] = []
    fields = set().union(*LAYER_FIELDS.values()) - {"project"}
    for field in sorted(fields):
        for item in _mapping_items(payload.get(field)):
            items.append((field, item))
    return items


def _collect_sources(payload: Mapping[str, Any]) -> list[str]:
    sources: list[str] = []
    seen: set[str] = set()
    project = payload.get("project")
    if isinstance(project, Mapping):
        label = _source_label(project)
        if label and label not in seen:
            seen.add(label)
            sources.append(label)
    for _, item in _selected_content_items(payload):
        label = _source_label(item)
        if label and label not in seen:
            seen.add(label)
            sources.append(label)
    return sources[:24]


def _verification(payload: Mapping[str, Any]) -> dict[str, Any]:
    items = [item for _, item in _selected_content_items(payload)]
    sourced = sum(_provenance(item) not in (None, "", [], {}) for item in items)
    untrusted = sum(
        item.get("trusted") is False
        or (
            isinstance(item.get("metadata"), Mapping)
            and (
                item["metadata"].get("untrusted") is True
                or item["metadata"].get("prompt_injection_detected") is True
            )
        )
        for item in items
    )
    if not items:
        status = "empty"
    elif untrusted:
        status = "mixed"
    elif sourced == len(items):
        status = "verified"
    elif sourced:
        status = "partial"
    else:
        status = "unverified"
    return {
        "status": status,
        "selected_items": len(items),
        "sourced_items": sourced,
        "untrusted_items": untrusted,
    }


def _next_safe_action(payload: Mapping[str, Any]) -> str | None:
    for field in ("checkpoints", "sessions", "tasks"):
        for item in _mapping_items(payload.get(field)):
            for key in ("next_step", "remaining_work"):
                value = item.get(key)
                if value not in (None, "", [], {}):
                    return _compact(value, 240)
    return None


def _block_metrics(
    source_context: Mapping[str, Any],
    payload: Mapping[str, Any],
    counter: TokenCounter,
) -> dict[str, dict[str, int]]:
    fields = sorted(set().union(*LAYER_FIELDS.values()))
    metrics: dict[str, dict[str, int]] = {}
    for field in fields:
        if field == "project":
            original = 1 if isinstance(source_context.get(field), Mapping) else 0
            selected = 1 if isinstance(payload.get(field), Mapping) else 0
            compressed = 0
            token_cost = counter.count(payload[field]) if selected else 0
        else:
            original_items = _mapping_items(source_context.get(field))
            selected_items = _mapping_items(payload.get(field))
            original = len(original_items)
            selected = len(selected_items)
            compressed = sum(isinstance(item.get("compression"), Mapping) for item in selected_items)
            token_cost = counter.count(selected_items) if selected_items else 0
        if original or selected:
            metrics[field] = {
                "selected_items": selected,
                "dropped_items": max(0, original - selected),
                "compressed_items": compressed,
                "tokens": token_cost,
            }
    return metrics


def _refresh_legacy_metrics(
    source_context: Mapping[str, Any],
    payload: dict[str, Any],
    counter: TokenCounter,
) -> None:
    metrics = payload.get("context_metrics")
    if not isinstance(metrics, dict):
        return
    blocks = _block_metrics(source_context, payload, counter)
    selected_items = sum(
        block["selected_items"] for field, block in blocks.items() if field != "project"
    )
    dropped_items = sum(
        block["dropped_items"] for field, block in blocks.items() if field != "project"
    )
    compressed_items = sum(block["compressed_items"] for block in blocks.values())
    metrics.update(
        {
            "selected_items": selected_items,
            "dropped_items": dropped_items,
            "compressed_items": compressed_items,
            "blocks": blocks,
        }
    )


def _packet_metadata(
    payload: Mapping[str, Any],
    *,
    intent: str,
    counter: TokenCounter,
    budget: int,
    effective_budget: int,
    safety_margin: float,
) -> dict[str, Any]:
    return {
        "version": CONTEXT_PACKET_VERSION,
        "objective": _compact(intent, 300) if intent else None,
        "next_safe_action": _next_safe_action(payload),
        "sources": _collect_sources(payload),
        "verification": _verification(payload),
        "tokens": {
            "budget": budget,
            "effective_content_budget": effective_budget,
            "safety_margin_percent": round(safety_margin * 100, 2),
            "count": 0,
            "estimated_count": 0,
            "tokenizer": counter.name,
            "model": counter.model,
            "mode": "exact" if counter.exact else "estimated",
            "fallback": not counter.exact,
            "estimation_error_tokens": None,
            "estimation_error_percent": None,
        },
    }


def _refresh_token_usage(payload: dict[str, Any], counter: TokenCounter) -> int:
    packet = payload.get("context_packet")
    if not isinstance(packet, dict):
        raise ValueError("context_packet metadata is missing")
    tokens = packet.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError("context_packet token metadata is missing")

    previous: tuple[int, int] | None = None
    for _ in range(8):
        measurement = measure_tokens(payload, counter)
        signature = (measurement.count, measurement.estimated_count)
        tokens.update(measurement.as_dict())
        if signature == previous:
            break
        previous = signature
    final = measure_tokens(payload, counter)
    tokens.update(final.as_dict())
    return final.count


def _drop_lowest_ranked_item(payload: dict[str, Any]) -> bool:
    candidates: list[tuple[float, int, str, int]] = []
    field_order = {field: index for index, field in enumerate(_REMOVABLE_FIELDS)}
    for field in _REMOVABLE_FIELDS:
        values = payload.get(field)
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                continue
            try:
                score = float(item.get("context_score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            candidates.append((score, field_order[field], field, index))
    if not candidates:
        return False
    _, _, field, index = min(candidates)
    values = payload[field]
    values.pop(index)
    if not values:
        payload.pop(field, None)
    return True


def build_context_packet(
    context: Mapping[str, Any],
    *,
    intent: str = "",
    layer: str = "operational",
    budget: int | None = None,
    model: str | None = None,
    tokenizer: str | TokenCounter | None = None,
    safety_margin: float = DEFAULT_SAFETY_MARGIN,
    include_untrusted: bool = False,
    compress_oversized: bool = True,
    item_budget: int = 180,
    fixed_fields: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ContextPacketResult:
    """Compile a versioned packet and enforce its final serialized token budget."""
    normalized_layer = layer.strip().lower()
    if normalized_layer not in LAYER_FIELDS:
        raise ValueError(f"Unknown context layer: {layer}")
    token_budget = int(budget or DEFAULT_BUDGETS[normalized_layer])
    if token_budget < MIN_CONTEXT_PACKET_BUDGET:
        raise ValueError(
            f"context packet budget must be at least {MIN_CONTEXT_PACKET_BUDGET} tokens"
        )
    if not 0.0 <= safety_margin < 0.5:
        raise ValueError("safety_margin must be between 0.0 and 0.5")

    counter = resolve_token_counter(model=model, tokenizer=tokenizer)
    effective_budget = max(128, int(token_budget * (1.0 - safety_margin)))
    legacy = build_context(
        context,
        intent=intent,
        layer=normalized_layer,
        budget=effective_budget,
        include_untrusted=include_untrusted,
        compress_oversized=compress_oversized,
        item_budget=item_budget,
        now=now,
    )
    output = dict(legacy.context)
    for key, value in (fixed_fields or {}).items():
        if key in {"context_packet", "context_policy", "context_metrics"}:
            raise ValueError(f"fixed field {key!r} is reserved by the Context Packet contract")
        output[key] = value
    _refresh_legacy_metrics(context, output, counter)
    output["context_packet"] = _packet_metadata(
        output,
        intent=intent,
        counter=counter,
        budget=token_budget,
        effective_budget=effective_budget,
        safety_margin=safety_margin,
    )

    while True:
        final_tokens = _refresh_token_usage(output, counter)
        if final_tokens <= effective_budget:
            break
        removed = _drop_lowest_ranked_item(output)
        if not removed:
            raise ValueError(
                "context packet control metadata and required project data exceed the token budget"
            )
        _refresh_legacy_metrics(context, output, counter)
        output["context_packet"] = _packet_metadata(
            output,
            intent=intent,
            counter=counter,
            budget=token_budget,
            effective_budget=effective_budget,
            safety_margin=safety_margin,
        )

    return ContextPacketResult(
        context=output,
        legacy_result=legacy,
        counter=counter,
        budget=token_budget,
        effective_budget=effective_budget,
    )
