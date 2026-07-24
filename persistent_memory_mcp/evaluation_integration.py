"""Bounded MCP integration for reproducible agent evaluation suites."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from .evaluation import EvaluationCase, evaluate_suite, provenance_record, token_savings_score

_ALLOWED_CATEGORIES = frozenset(
    {
        "targeting",
        "duplicate_avoidance",
        "wrong_target_prevention",
        "stale_detection",
        "continuation",
        "prompt_injection_resistance",
        "handoff",
        "provenance",
    }
)


def _parse_cases(values: Sequence[Mapping[str, Any]]) -> list[EvaluationCase]:
    if len(values) > 500:
        raise ValueError("evaluation suites are limited to 500 cases")
    cases: list[EvaluationCase] = []
    for index, value in enumerate(values):
        category = str(value.get("category") or "").strip()
        if category not in _ALLOWED_CATEGORIES:
            raise ValueError(f"unsupported evaluation category at index {index}: {category}")
        name = str(value.get("name") or "").strip()
        if not name:
            raise ValueError(f"case name is required at index {index}")
        cases.append(
            EvaluationCase(
                name=name,
                category=category,
                expected=value.get("expected"),
                observed=value.get("observed"),
                weight=float(value.get("weight", 1.0)),
                source=str(value["source"]) if value.get("source") is not None else None,
                verification_state=str(value.get("verification_state") or "unverified"),
                confidence=float(value.get("confidence", 1.0)),
            )
        )
    return cases


def build_evaluation_tool(_server_module: Any) -> Callable[..., dict[str, Any]]:
    """Build a pure, bounded evaluator that does not execute user-provided code."""

    def run_agent_evaluation(
        cases: Sequence[Mapping[str, Any]],
        *,
        categories: Sequence[str] | None = None,
        baseline_tokens: int | None = None,
        actual_tokens: int | None = None,
        quality_floor: float = 0.8,
    ) -> dict[str, Any]:
        try:
            parsed = _parse_cases(cases)
        except (TypeError, ValueError) as exc:
            return {"error": str(exc)}
        selected = list(categories or sorted({case.category for case in parsed}))
        unsupported = sorted(set(selected) - _ALLOWED_CATEGORIES)
        if unsupported:
            return {"error": f"unsupported categories: {', '.join(unsupported)}"}
        result = evaluate_suite(parsed, categories=selected)
        result["provenance"] = [
            provenance_record(
                fact={"case": case.name, "expected": case.expected, "observed": case.observed},
                source=case.source,
                verification_state=case.verification_state,
                confidence=case.confidence,
                evidence=["deterministic expected-versus-observed comparison"],
            )
            for case in parsed
        ]
        if baseline_tokens is not None or actual_tokens is not None:
            if baseline_tokens is None or actual_tokens is None:
                return {"error": "baseline_tokens and actual_tokens must be provided together"}
            try:
                result["token_efficiency"] = token_savings_score(
                    baseline_tokens=baseline_tokens,
                    actual_tokens=actual_tokens,
                    quality_score=float(result["overall_score"]),
                    quality_floor=quality_floor,
                )
            except ValueError as exc:
                return {"error": str(exc)}
        return {"status": "ok", "evaluation": result}

    run_agent_evaluation.__name__ = "run_agent_evaluation"
    return run_agent_evaluation


def install_agent_evaluation(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Install the evaluator once without mutating existing server behavior."""
    if getattr(server_module, "_agent_evaluation_installed", False):
        return server_module.run_agent_evaluation
    tool = build_evaluation_tool(server_module)
    server_module.run_agent_evaluation = tool
    try:
        server_module.server.tool(
            name="run_agent_evaluation",
            description="Ejecuta suites acotadas y reproducibles de evaluación de agentes.",
        )(tool)
    except Exception:
        pass
    server_module._agent_evaluation_installed = True
    return tool
