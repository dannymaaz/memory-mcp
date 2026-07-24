"""Deterministic evaluation and provenance utilities for memory-assisted agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class EvaluationCase:
    """One reproducible expected-versus-observed agent behavior."""

    name: str
    category: str
    expected: Any
    observed: Any
    weight: float = 1.0
    source: str | None = None
    verification_state: str = "unverified"
    confidence: float = 1.0


@dataclass(frozen=True)
class EvaluationMetric:
    """A bounded metric with transparent evidence."""

    category: str
    score: float
    passed: int
    total: int
    weighted_passed: float
    weighted_total: float
    evidence: tuple[dict[str, Any], ...]


def _normalized(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())
    if isinstance(value, Mapping):
        return {str(key): _normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalized(item) for item in value]
    return value


def case_passed(case: EvaluationCase) -> bool:
    """Compare expected and observed values deterministically."""
    return _normalized(case.expected) == _normalized(case.observed)


def evaluate_cases(cases: Iterable[EvaluationCase], *, category: str) -> EvaluationMetric:
    """Aggregate one evaluation category with weighted evidence."""
    selected = [case for case in cases if case.category == category]
    if not selected:
        return EvaluationMetric(category, 0.0, 0, 0, 0.0, 0.0, ())
    weighted_total = sum(max(0.0, case.weight) for case in selected)
    evidence: list[dict[str, Any]] = []
    passed = 0
    weighted_passed = 0.0
    for case in selected:
        success = case_passed(case)
        weight = max(0.0, case.weight)
        if success:
            passed += 1
            weighted_passed += weight
        evidence.append(
            {
                "name": case.name,
                "passed": success,
                "weight": weight,
                "expected": case.expected,
                "observed": case.observed,
                "source": case.source,
                "verification_state": case.verification_state,
                "confidence": max(0.0, min(1.0, case.confidence)),
            }
        )
    score = weighted_passed / weighted_total if weighted_total else 0.0
    return EvaluationMetric(
        category=category,
        score=score,
        passed=passed,
        total=len(selected),
        weighted_passed=weighted_passed,
        weighted_total=weighted_total,
        evidence=tuple(evidence),
    )


def token_savings_score(*, baseline_tokens: int, actual_tokens: int, quality_score: float, quality_floor: float = 0.8) -> dict[str, Any]:
    """Measure token savings only when the fixed quality threshold is met."""
    if baseline_tokens <= 0 or actual_tokens < 0:
        raise ValueError("token counts must be non-negative and baseline_tokens must be positive")
    quality_score = max(0.0, min(1.0, quality_score))
    savings = max(0, baseline_tokens - actual_tokens)
    ratio = savings / baseline_tokens
    return {
        "baseline_tokens": baseline_tokens,
        "actual_tokens": actual_tokens,
        "saved_tokens": savings,
        "savings_ratio": ratio,
        "quality_score": quality_score,
        "quality_floor": quality_floor,
        "qualified": quality_score >= quality_floor,
        "effective_score": ratio if quality_score >= quality_floor else 0.0,
    }


def provenance_record(*, fact: Any, source: str | None, verification_state: str, confidence: float, evidence: Sequence[str] | None = None) -> dict[str, Any]:
    """Explain where an important fact came from and how trustworthy it is."""
    confidence = max(0.0, min(1.0, confidence))
    return {
        "fact": fact,
        "source": source,
        "verification_state": verification_state,
        "confidence": confidence,
        "evidence": list(evidence or []),
        "explainable": bool(source and verification_state and evidence),
    }


def evaluate_suite(cases: Iterable[EvaluationCase], *, categories: Sequence[str]) -> dict[str, Any]:
    """Return deterministic category metrics plus a weighted overall score."""
    case_list = list(cases)
    metrics = [evaluate_cases(case_list, category=category) for category in categories]
    weighted_total = sum(metric.weighted_total for metric in metrics)
    weighted_passed = sum(metric.weighted_passed for metric in metrics)
    return {
        "overall_score": weighted_passed / weighted_total if weighted_total else 0.0,
        "categories": [asdict(metric) for metric in metrics],
        "case_count": sum(metric.total for metric in metrics),
    }
