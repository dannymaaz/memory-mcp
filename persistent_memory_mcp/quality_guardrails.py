"""Deterministic Context Compiler quality-threshold evaluation."""

from __future__ import annotations

from typing import Any, Mapping


_REQUIRED_THRESHOLDS = {
    "file_recall_at_5_min",
    "symbol_recall_at_8_min",
    "file_precision_at_5_min",
    "symbol_precision_at_8_min",
    "token_fit_rate_min",
    "token_savings_rate_min",
    "provenance_coverage_min",
    "max_task_latency_ms",
    "safety_pass_rate_min",
}


def evaluate_quality_thresholds(
    aggregate: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> dict[str, bool]:
    """Return explicit per-metric gates; missing inputs fail closed."""
    missing_thresholds = sorted(_REQUIRED_THRESHOLDS - set(thresholds))
    if missing_thresholds:
        raise ValueError(f"missing quality thresholds: {missing_thresholds}")

    def number(name: str) -> float:
        value = aggregate.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return float("-inf")
        return float(value)

    return {
        "file_recall_at_5": number("file_recall_at_5")
        >= float(thresholds["file_recall_at_5_min"]),
        "file_precision_at_5": number("file_precision_at_5")
        >= float(thresholds["file_precision_at_5_min"]),
        "symbol_recall_at_8": number("symbol_recall_at_8")
        >= float(thresholds["symbol_recall_at_8_min"]),
        "symbol_precision_at_8": number("symbol_precision_at_8")
        >= float(thresholds["symbol_precision_at_8_min"]),
        "token_fit_rate": number("token_fit_rate") >= float(thresholds["token_fit_rate_min"]),
        "token_savings_rate": number("token_savings_rate")
        >= float(thresholds["token_savings_rate_min"]),
        "provenance_coverage": number("provenance_coverage")
        >= float(thresholds["provenance_coverage_min"]),
        "latency": number("max_task_latency_ms") <= float(thresholds["max_task_latency_ms"]),
        "safety_pass_rate": number("safety_pass_rate")
        >= float(thresholds["safety_pass_rate_min"]),
    }


def quality_gate_passes(aggregate: Mapping[str, Any], thresholds: Mapping[str, Any]) -> bool:
    """Return true only when every independent quality/safety gate passes."""
    return all(evaluate_quality_thresholds(aggregate, thresholds).values())
