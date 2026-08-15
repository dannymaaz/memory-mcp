"""Measure deterministic fallback error against the optional tiktoken reference."""

from __future__ import annotations

import json
from pathlib import Path

from persistent_memory_mcp.tokenization import measure_tokens, resolve_token_counter

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE_NAMES = ("tokenization_spanish.txt", "tokenization_code.py")
REFERENCE_MODEL = "gpt-4o"
MAX_ERROR_PERCENT = 40.0


def evaluate() -> dict[str, object]:
    reference = resolve_token_counter(model=REFERENCE_MODEL, tokenizer="tiktoken")
    results: list[dict[str, object]] = []
    for fixture_name in FIXTURE_NAMES:
        payload = (FIXTURES / fixture_name).read_text(encoding="utf-8")
        measurement = measure_tokens(payload, reference)
        results.append(
            {
                "fixture": fixture_name,
                "reference_tokens": measurement.count,
                "fallback_tokens": measurement.estimated_count,
                "absolute_error_tokens": measurement.estimation_error_tokens,
                "error_percent": measurement.estimation_error_percent,
            }
        )
    worst_error = max(float(item["error_percent"] or 0.0) for item in results)
    return {
        "reference_model": REFERENCE_MODEL,
        "reference_tokenizer": reference.name,
        "fallback_tokenizer": "deterministic-heuristic-v2",
        "max_allowed_error_percent": MAX_ERROR_PERCENT,
        "worst_error_percent": worst_error,
        "fixtures": results,
        "within_guardrail": worst_error <= MAX_ERROR_PERCENT,
    }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["within_guardrail"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
