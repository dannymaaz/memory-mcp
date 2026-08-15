"""Evaluate bounded repository retrieval on a reproducible synthetic repository."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from persistent_memory_mcp.repository_retrieval import (
    ProgressiveRepositoryRetriever,
    RetrievalLimits,
)

FILE_COUNT = 80
MAX_FILES_PARSED = 6
TOKEN_BUDGET = 1400
MAX_FRAGMENT_RATIO = 0.35


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


def _build_repository(root: Path) -> Path:
    repo = root / "repository"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "evaluation@example.com")
    _git(repo, "config", "user.name", "Memory MCP Evaluation")

    target_lines = [
        '"""Authentication service used by the retrieval evaluation."""',
        "",
        "def validate_access_token(token: str) -> bool:",
        "    normalized = token.strip()",
        "    " + "return normalized.startswith('Bearer ') and len(normalized) > 12",
        "",
    ]
    target_lines.extend(f"# authentication background line {index}" for index in range(1, 120))
    _write(repo, "services/security.py", "\n".join(target_lines) + "\n")

    for index in range(FILE_COUNT - 1):
        _write(
            repo,
            f"modules/domain_{index:03d}.py",
            f"def unrelated_domain_{index}():\n    return {index}\n",
        )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "evaluation fixture")
    return repo


def evaluate() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="memory-mcp-retrieval-") as temp_name:
        repo = _build_repository(Path(temp_name))
        limits = RetrievalLimits(
            max_index_files=200,
            max_files=MAX_FILES_PARSED,
            max_symbols=20,
            max_neighbors=4,
            max_fragments=3,
            max_fragment_lines=18,
            max_total_bytes=8_000,
            page_size=6,
            token_budget=TOKEN_BUDGET,
        )
        result = ProgressiveRepositoryRetriever().retrieve(
            str(repo),
            "validate_access_token",
            limits=limits,
            tokenizer="deterministic",
        )
        target = next(
            fragment
            for fragment in result["fragments"]
            if fragment["symbol"] == "validate_access_token"
        )
        target_file = repo / target["path"]
        total_lines = len(target_file.read_text(encoding="utf-8").splitlines())
        fragment_lines = int(target["end_line"]) - int(target["start_line"]) + 1
        fragment_ratio = round(fragment_lines / max(1, total_lines), 4)
        mapped_files = int(result["repository_map"][0]["files"])
        parsed_files = int(result["index"]["files_scanned"])
        fragment_bytes = sum(int(item["bytes"]) for item in result["fragments"])
        token_count = int(result["token_usage"]["count"])
        report = {
            "mapped_supported_files": mapped_files,
            "parsed_candidate_files": parsed_files,
            "parse_fraction": round(parsed_files / max(1, mapped_files), 4),
            "selected_fragments": len(result["fragments"]),
            "fragment_bytes": fragment_bytes,
            "target_file_lines": total_lines,
            "target_fragment_lines": fragment_lines,
            "target_fragment_ratio": fragment_ratio,
            "token_count": token_count,
            "token_budget": TOKEN_BUDGET,
            "top_file": result["file_candidates"][0]["path"],
            "top_fragment": target["path"],
            "within_limits": (
                mapped_files == FILE_COUNT
                and parsed_files <= MAX_FILES_PARSED
                and fragment_ratio <= MAX_FRAGMENT_RATIO
                and token_count <= TOKEN_BUDGET
                and target["path"] == "services/security.py"
            ),
        }
        return report


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["within_limits"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
