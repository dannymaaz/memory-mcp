from __future__ import annotations

import pytest

from persistent_memory_mcp.quality_guardrails import (
    evaluate_quality_thresholds,
    quality_gate_passes,
)


THRESHOLDS = {
    "file_recall_at_5_min": 1.0,
    "symbol_recall_at_8_min": 1.0,
    "file_precision_at_5_min": 0.2,
    "symbol_precision_at_8_min": 0.125,
    "token_fit_rate_min": 1.0,
    "token_savings_rate_min": 0.4,
    "provenance_coverage_min": 1.0,
    "max_task_latency_ms": 20_000,
    "safety_pass_rate_min": 1.0,
}

BASELINE = {
    "file_recall_at_5": 1.0,
    "symbol_recall_at_8": 1.0,
    "file_precision_at_5": 0.2,
    "symbol_precision_at_8": 0.125,
    "token_fit_rate": 1.0,
    "token_savings_rate": 0.77,
    "provenance_coverage": 1.0,
    "max_task_latency_ms": 150,
    "safety_pass_rate": 1.0,
}


def test_baseline_passes_all_independent_quality_gates() -> None:
    checks = evaluate_quality_thresholds(BASELINE, THRESHOLDS)

    assert all(checks.values())
    assert quality_gate_passes(BASELINE, THRESHOLDS) is True


@pytest.mark.parametrize(
    ("metric", "regressed"),
    [
        ("file_recall_at_5", 0.75),
        ("symbol_recall_at_8", 0.75),
        ("token_fit_rate", 0.75),
        ("token_savings_rate", 0.1),
        ("provenance_coverage", 0.75),
        ("safety_pass_rate", 0.5),
        ("max_task_latency_ms", 25_000),
    ],
)
def test_deliberate_regression_fails_the_guard(metric: str, regressed: float) -> None:
    degraded = dict(BASELINE)
    degraded[metric] = regressed

    checks = evaluate_quality_thresholds(degraded, THRESHOLDS)

    assert quality_gate_passes(degraded, THRESHOLDS) is False
    assert any(value is False for value in checks.values())


def test_missing_aggregate_metric_fails_closed() -> None:
    incomplete = dict(BASELINE)
    incomplete.pop("provenance_coverage")

    checks = evaluate_quality_thresholds(incomplete, THRESHOLDS)

    assert checks["provenance_coverage"] is False
    assert quality_gate_passes(incomplete, THRESHOLDS) is False


def test_missing_threshold_is_configuration_error() -> None:
    incomplete = dict(THRESHOLDS)
    incomplete.pop("token_fit_rate_min")

    with pytest.raises(ValueError, match="missing quality thresholds"):
        evaluate_quality_thresholds(BASELINE, incomplete)
