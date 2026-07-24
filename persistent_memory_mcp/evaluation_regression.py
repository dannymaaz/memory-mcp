"""Checked-in regression runner for deterministic agent evaluation fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluation import EvaluationCase, evaluate_suite


def load_evaluation_fixture(path: str | Path) -> dict[str, Any]:
    """Load and validate a bounded JSON evaluation fixture."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases")
    categories = payload.get("categories")
    thresholds = payload.get("thresholds")
    if not isinstance(cases, list) or not isinstance(categories, list) or not isinstance(thresholds, dict):
        raise ValueError("fixture requires cases, categories and thresholds")
    if not cases or len(cases) > 500:
        raise ValueError("fixture must contain between 1 and 500 cases")
    return payload


def run_regression_fixture(path: str | Path) -> dict[str, Any]:
    """Evaluate a fixture and report threshold failures deterministically."""
    payload = load_evaluation_fixture(path)
    cases = [EvaluationCase(**item) for item in payload["cases"]]
    result = evaluate_suite(cases, categories=payload["categories"])
    scores = {item["category"]: item["score"] for item in result["categories"]}
    scores["overall_score"] = result["overall_score"]
    failures = [
        {"metric": metric, "score": scores.get(metric, 0.0), "threshold": float(threshold)}
        for metric, threshold in sorted(payload["thresholds"].items())
        if scores.get(metric, 0.0) < float(threshold)
    ]
    return {**result, "scores": scores, "threshold_failures": failures, "passed": not failures}


def main() -> int:
    """Run the checked-in core suite for CI."""
    root = Path(__file__).resolve().parents[1]
    result = run_regression_fixture(root / "evaluation_scenarios" / "core.json")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
