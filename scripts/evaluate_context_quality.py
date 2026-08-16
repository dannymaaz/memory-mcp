"""Evaluate Context Compiler retrieval quality against a versioned local golden corpus."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from persistent_memory_mcp.repository_retrieval import (
    ProgressiveRepositoryRetriever,
    RetrievalLimits,
)
from persistent_memory_mcp.tokenization import measure_tokens, resolve_token_counter

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "tests" / "fixtures" / "context_quality_corpus.json"
THRESHOLDS_PATH = ROOT / "tests" / "fixtures" / "context_quality_thresholds.json"
TOKEN_BUDGET = 1800
FILE_K = 5
SYMBOL_K = 8
DISTRACTOR_COUNT = 36


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _padding(topic: str, count: int = 80) -> str:
    return "\n".join(f"# {topic} implementation note {index}" for index in range(1, count + 1))


def _build_repository(root: Path) -> Path:
    repo = root / "repository"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "context-quality@example.com")
    _git(repo, "config", "user.name", "Context Quality Evaluation")

    _write(
        repo,
        "services/security.py",
        '"""Authentication access-token validation."""\n\n'
        "def validate_access_token(token: str) -> bool:\n"
        "    normalized = token.strip()\n"
        "    return normalized.startswith('Bearer ') and len(normalized) > 12\n\n"
        + _padding("authentication bearer token"),
    )
    _write(
        repo,
        "billing/invoice.py",
        '"""Invoice billing calculations."""\n\n'
        "def calculate_invoice_total(subtotal: float, tax: float) -> float:\n"
        "    return round(subtotal + tax, 2)\n\n"
        + _padding("invoice billing total"),
    )
    _write(
        repo,
        "sessions/lifecycle.py",
        '"""Session expiration lifecycle."""\n\n'
        "def is_session_expired(age_seconds: int, ttl_seconds: int) -> bool:\n"
        "    return age_seconds >= ttl_seconds\n\n"
        + _padding("session expiry ttl lifecycle"),
    )
    _write(
        repo,
        "web/cart.ts",
        "export function applyCartDiscount(total: number, discount: number) {\n"
        "  return Math.max(0, total - discount);\n"
        "}\n\n"
        + _padding("cart discount checkout promotion"),
    )

    for index in range(DISTRACTOR_COUNT):
        _write(
            repo,
            f"modules/domain_{index:03d}.py",
            f"def unrelated_domain_{index}(value: int) -> int:\n"
            f"    return value + {index}\n\n"
            + _padding(f"unrelated domain {index}", 10),
        )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "context quality golden fixture")
    return repo


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _recall(expected: set[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    return len(expected.intersection(observed)) / len(expected)


def _precision(expected: set[str], observed: list[str]) -> float:
    if not observed:
        return 0.0
    return len(expected.intersection(observed)) / len(observed)


def _repository_token_baseline(repo: Path) -> int:
    counter = resolve_token_counter(tokenizer="deterministic")
    chunks: list[str] = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".sql"}:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return measure_tokens("\n".join(chunks), counter).count


def _provenance_complete(fragment: dict[str, Any]) -> bool:
    provenance = fragment.get("provenance") or {}
    required_fragment = {"path", "start_line", "end_line", "content_sha256", "file_sha256"}
    required_provenance = {"repository", "commit", "ref", "path", "start_line", "end_line"}
    return required_fragment.issubset(fragment) and required_provenance.issubset(provenance)


def evaluate() -> dict[str, Any]:
    corpus = _load_json(CORPUS_PATH)
    threshold_doc = _load_json(THRESHOLDS_PATH)
    thresholds = threshold_doc["thresholds"]

    with tempfile.TemporaryDirectory(prefix="memory-mcp-context-quality-") as temp_name:
        repo = _build_repository(Path(temp_name))
        baseline_tokens = _repository_token_baseline(repo)
        retriever = ProgressiveRepositoryRetriever()
        limits = RetrievalLimits(
            max_index_files=200,
            max_files=8,
            max_symbols=40,
            max_neighbors=8,
            max_fragments=6,
            max_fragment_lines=18,
            max_total_bytes=16_000,
            page_size=SYMBOL_K,
            token_budget=TOKEN_BUDGET,
        )

        task_reports: list[dict[str, Any]] = []
        for task in corpus["tasks"]:
            started = time.perf_counter()
            result = retriever.retrieve(
                str(repo),
                str(task["query"]),
                limits=limits,
                tokenizer="deterministic",
            )
            latency_ms = (time.perf_counter() - started) * 1000.0

            expected_files = set(task["expected_files"])
            expected_symbols = set(task["expected_symbols"])
            observed_files = [
                str(item["path"]) for item in result["file_candidates"][:FILE_K]
            ]
            observed_symbols = [
                str(item["name"]) for item in result["symbol_candidates"][:SYMBOL_K]
            ]
            relevant_fragments = [
                fragment
                for fragment in result["fragments"]
                if fragment.get("path") in expected_files
                or fragment.get("symbol") in expected_symbols
            ]
            provenance_coverage = (
                sum(1 for item in relevant_fragments if _provenance_complete(item))
                / len(relevant_fragments)
                if relevant_fragments
                else 0.0
            )
            token_count = int(result["token_usage"]["count"])
            token_fit = token_count <= TOKEN_BUDGET
            savings = 1.0 - (token_count / max(1, baseline_tokens))
            task_reports.append(
                {
                    "id": task["id"],
                    "file_recall_at_5": round(_recall(expected_files, observed_files), 4),
                    "file_precision_at_5": round(_precision(expected_files, observed_files), 4),
                    "symbol_recall_at_8": round(_recall(expected_symbols, observed_symbols), 4),
                    "symbol_precision_at_8": round(_precision(expected_symbols, observed_symbols), 4),
                    "token_count": token_count,
                    "token_budget": TOKEN_BUDGET,
                    "token_fit": token_fit,
                    "token_savings_rate": round(savings, 4),
                    "provenance_coverage": round(provenance_coverage, 4),
                    "latency_ms": round(latency_ms, 2),
                    "top_files": observed_files,
                    "top_symbols": observed_symbols,
                }
            )

        count = len(task_reports)
        aggregate = {
            "file_recall_at_5": round(sum(item["file_recall_at_5"] for item in task_reports) / count, 4),
            "file_precision_at_5": round(sum(item["file_precision_at_5"] for item in task_reports) / count, 4),
            "symbol_recall_at_8": round(sum(item["symbol_recall_at_8"] for item in task_reports) / count, 4),
            "symbol_precision_at_8": round(sum(item["symbol_precision_at_8"] for item in task_reports) / count, 4),
            "token_fit_rate": round(sum(1 for item in task_reports if item["token_fit"]) / count, 4),
            "token_savings_rate": round(sum(item["token_savings_rate"] for item in task_reports) / count, 4),
            "provenance_coverage": round(sum(item["provenance_coverage"] for item in task_reports) / count, 4),
            "max_task_latency_ms": round(max(item["latency_ms"] for item in task_reports), 2),
        }
        safety_checks = {
            "all_tasks_within_hard_token_budget": aggregate["token_fit_rate"] == 1.0,
            "all_expected_evidence_has_provenance": aggregate["provenance_coverage"] == 1.0,
        }
        safety_pass_rate = sum(1 for value in safety_checks.values() if value) / len(safety_checks)
        aggregate["safety_pass_rate"] = round(safety_pass_rate, 4)

        checks = {
            "file_recall_at_5": aggregate["file_recall_at_5"] >= thresholds["file_recall_at_5_min"],
            "file_precision_at_5": aggregate["file_precision_at_5"] >= thresholds["file_precision_at_5_min"],
            "symbol_recall_at_8": aggregate["symbol_recall_at_8"] >= thresholds["symbol_recall_at_8_min"],
            "symbol_precision_at_8": aggregate["symbol_precision_at_8"] >= thresholds["symbol_precision_at_8_min"],
            "token_fit_rate": aggregate["token_fit_rate"] >= thresholds["token_fit_rate_min"],
            "token_savings_rate": aggregate["token_savings_rate"] >= thresholds["token_savings_rate_min"],
            "provenance_coverage": aggregate["provenance_coverage"] >= thresholds["provenance_coverage_min"],
            "latency": aggregate["max_task_latency_ms"] <= thresholds["max_task_latency_ms"],
            "safety_pass_rate": aggregate["safety_pass_rate"] >= thresholds["safety_pass_rate_min"],
        }
        return {
            "passed": all(checks.values()),
            "fixture_version": corpus["version"],
            "threshold_version": threshold_doc["version"],
            "evaluator_version": threshold_doc["evaluator_version"],
            "tokenizer": "deterministic-heuristic-v2",
            "model": None,
            "repository_baseline_tokens": baseline_tokens,
            "tasks": task_reports,
            "aggregate": aggregate,
            "safety_checks": safety_checks,
            "checks": checks,
            "thresholds": thresholds,
        }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
