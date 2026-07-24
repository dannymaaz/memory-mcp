from __future__ import annotations

from persistent_memory_mcp.evaluation import (
    EvaluationCase,
    case_passed,
    evaluate_cases,
    evaluate_suite,
    provenance_record,
    token_savings_score,
)


def test_case_comparison_normalizes_strings_and_mappings() -> None:
    case = EvaluationCase(
        name="project selection",
        category="targeting",
        expected={"project": "Memory MCP", "service": " API "},
        observed={"service": "api", "project": "memory   mcp"},
    )
    assert case_passed(case) is True


def test_weighted_metric_preserves_evidence() -> None:
    cases = [
        EvaluationCase("correct", "targeting", "api", "api", weight=2, source="git"),
        EvaluationCase("wrong", "targeting", "api", "worker", weight=1, source="memory"),
    ]
    metric = evaluate_cases(cases, category="targeting")
    assert metric.score == 2 / 3
    assert metric.passed == 1
    assert metric.total == 2
    assert metric.evidence[1]["passed"] is False


def test_suite_aggregates_categories_deterministically() -> None:
    cases = [
        EvaluationCase("project", "targeting", "a", "a"),
        EvaluationCase("duplicate", "duplicate_avoidance", True, True),
        EvaluationCase("stale", "stale_detection", "stale", "verified"),
    ]
    result = evaluate_suite(
        cases,
        categories=("targeting", "duplicate_avoidance", "stale_detection"),
    )
    assert result["case_count"] == 3
    assert result["overall_score"] == 2 / 3


def test_token_savings_requires_quality_floor() -> None:
    qualified = token_savings_score(
        baseline_tokens=1000,
        actual_tokens=400,
        quality_score=0.9,
    )
    disqualified = token_savings_score(
        baseline_tokens=1000,
        actual_tokens=300,
        quality_score=0.7,
    )
    assert qualified["effective_score"] == 0.6
    assert disqualified["effective_score"] == 0.0


def test_provenance_is_explainable_only_with_complete_evidence() -> None:
    complete = provenance_record(
        fact="HEAD is abc",
        source="git:HEAD",
        verification_state="verified",
        confidence=1.2,
        evidence=["git rev-parse HEAD"],
    )
    incomplete = provenance_record(
        fact="HEAD is abc",
        source=None,
        verification_state="unverified",
        confidence=-1,
    )
    assert complete["confidence"] == 1.0
    assert complete["explainable"] is True
    assert incomplete["confidence"] == 0.0
    assert incomplete["explainable"] is False


def test_empty_category_is_bounded() -> None:
    metric = evaluate_cases([], category="handoff")
    assert metric.score == 0.0
    assert metric.total == 0
