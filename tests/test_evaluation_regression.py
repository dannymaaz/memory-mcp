from __future__ import annotations

import json

import pytest

from persistent_memory_mcp.evaluation_regression import load_evaluation_fixture, run_regression_fixture


def test_checked_in_core_fixture_passes() -> None:
    result = run_regression_fixture("evaluation_scenarios/core.json")
    assert result["passed"] is True
    assert result["threshold_failures"] == []
    assert result["case_count"] == 7


def test_regression_reports_failed_threshold(tmp_path) -> None:
    fixture = {
        "categories": ["targeting"],
        "thresholds": {"overall_score": 1.0, "targeting": 1.0},
        "cases": [{"name": "wrong target", "category": "targeting", "expected": "a", "observed": "b"}],
    }
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = run_regression_fixture(path)
    assert result["passed"] is False
    assert {item["metric"] for item in result["threshold_failures"]} == {"overall_score", "targeting"}


def test_fixture_is_bounded(tmp_path) -> None:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps({"categories": [], "thresholds": {}, "cases": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="between 1 and 500"):
        load_evaluation_fixture(path)
