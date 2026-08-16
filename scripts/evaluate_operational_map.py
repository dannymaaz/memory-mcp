"""Evaluate bounded operational-map latency, isolation and payload safety locally."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from persistent_memory_mcp.operational_map import OperationalMapLimits, OperationalMapService
from persistent_memory_mcp.storage import SQLiteStorage

OWNER = "operational-eval-owner"
PROJECT_COUNT = 20
FOCUS_SYMBOLS = 120
FOCUS_FILES = 12
FOCUS_TASKS = 20
MAX_OVERVIEW_MS = 5_000.0
MAX_GRAPH_MS = 5_000.0
LIMITS = OperationalMapLimits(
    max_projects=20,
    max_repositories=12,
    max_nodes=180,
    max_edges=400,
    max_records_per_kind=50,
)


def _seed(storage: SQLiteStorage) -> str:
    workspace = storage.insert(
        "workspaces",
        {"owner_id": OWNER, "name": "Operational Evaluation", "slug": "operational-evaluation"},
    )
    projects: list[dict[str, object]] = []
    for index in range(PROJECT_COUNT):
        project = storage.insert(
            "projects",
            {
                "workspace_id": workspace["id"],
                "owner_id": OWNER,
                "name": f"Project {index:02d}",
                "slug": f"project-{index:02d}",
                "repo_path": f"/private/evaluation/project-{index:02d}",
                "repo_remote": f"https://example.invalid/evaluation/project-{index:02d}.git",
                "repo_branch": "main",
                "repo_last_commit": f"{index + 1:040x}"[-40:],
                "repo_status": {"dirty": False},
            },
        )
        projects.append(project)

    focus = projects[0]
    focus_id = str(focus["id"])
    repository = str(focus["repo_path"])
    run_id = "operational-eval-run"
    commit = "f" * 40
    storage.insert(
        "code_symbol_snapshot_runs",
        {
            "id": run_id,
            "owner_id": OWNER,
            "project_id": focus_id,
            "repository": repository,
            "commit_sha": commit,
            "ref": "main",
            "symbol_count": FOCUS_SYMBOLS,
            "captured_at": "2026-08-15 12:00:00",
        },
    )

    symbols_per_file = FOCUS_SYMBOLS // FOCUS_FILES
    for index in range(FOCUS_SYMBOLS):
        logical_id = f"logical-{index:03d}"
        file_index = min(index // symbols_per_file, FOCUS_FILES - 1)
        snapshot_id = f"snapshot-{index:03d}"
        storage.insert(
            "code_symbol_snapshots",
            {
                "id": snapshot_id,
                "run_id": run_id,
                "owner_id": OWNER,
                "project_id": focus_id,
                "repository": repository,
                "commit_sha": commit,
                "ref": "main",
                "logical_id": logical_id,
                "source_symbol_id": f"source-{index:03d}",
                "path": f"src/module_{file_index:02d}.py",
                "name": f"symbol_{index:03d}",
                "qualified_name": f"module_{file_index:02d}.symbol_{index:03d}",
                "kind": "function",
                "language": "python",
                "line": index * 3 + 1,
                "end_line": index * 3 + 3,
                "signature": f"def symbol_{index:03d}():",
                "signature_sha256": f"{index + 1:064x}"[-64:],
                "body_sha256": f"{index + 2:064x}"[-64:],
                "file_sha256": f"{file_index + 3:064x}"[-64:],
                "first_seen_commit": commit,
                "verification_state": "verified",
            },
        )
        storage.insert(
            "code_symbol_changes",
            {
                "owner_id": OWNER,
                "project_id": focus_id,
                "repository": repository,
                "to_run_id": run_id,
                "to_commit": commit,
                "logical_id": logical_id,
                "new_snapshot_id": snapshot_id,
                "change_type": "added" if index < 24 else "unchanged",
            },
        )

    for index in range(FOCUS_TASKS):
        task = storage.insert(
            "tasks",
            {
                "owner_id": OWNER,
                "project_id": focus_id,
                "title": (
                    "Rotate sk-proj-abcdefghijklmnop123456789 safely"
                    if index == 0
                    else f"Operational task {index:02d}"
                ),
                "status": "blocked" if index == 0 else "pending",
                "priority": "high" if index == 0 else "medium",
            },
        )
        storage.insert(
            "code_symbol_links",
            {
                "owner_id": OWNER,
                "project_id": focus_id,
                "repository": repository,
                "logical_id": f"logical-{index:03d}",
                "snapshot_id": f"snapshot-{index:03d}",
                "relation_type": "implements",
                "target_type": "task",
                "target_id": str(task["id"]),
                "verification_state": "verified",
            },
        )

    # Other projects exercise the global overview without adding an unbounded graph fixture.
    for index, project in enumerate(projects[1:], start=1):
        project_id = str(project["id"])
        repo = str(project["repo_path"])
        storage.insert(
            "code_symbol_snapshot_runs",
            {
                "id": f"run-{index:02d}",
                "owner_id": OWNER,
                "project_id": project_id,
                "repository": repo,
                "commit_sha": f"{index + 20:040x}"[-40:],
                "ref": "main",
                "symbol_count": 0,
                "captured_at": "2026-08-15 12:00:00",
            },
        )

    foreign_workspace = storage.insert(
        "workspaces",
        {"owner_id": "foreign-owner", "name": "Foreign", "slug": "foreign"},
    )
    storage.insert(
        "projects",
        {
            "workspace_id": foreign_workspace["id"],
            "owner_id": "foreign-owner",
            "name": "Foreign project must stay isolated",
            "slug": "foreign-project",
        },
    )
    return focus_id


def evaluate() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="memory-mcp-operational-map-") as temp_name:
        storage = SQLiteStorage(Path(temp_name) / "memory.db")
        storage.initialize()
        focus_id = _seed(storage)
        service = OperationalMapService(storage, owner_id=OWNER)

        started = time.perf_counter()
        overview = service.project_overview(limits=LIMITS)
        overview_ms = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        graph = service.impact_graph(focus_id, limits=LIMITS)
        graph_ms = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        changed = service.impact_graph(focus_id, limits=LIMITS, changed_only=True)
        changed_ms = (time.perf_counter() - started) * 1000.0

        serialized = json.dumps(graph, ensure_ascii=False, sort_keys=True)
        changed_serialized = json.dumps(changed, ensure_ascii=False, sort_keys=True)
        project_ids = {str(item["project_id"]) for item in overview["projects"]}
        checks = {
            "overview_owner_isolated": len(project_ids) == PROJECT_COUNT,
            "overview_bounded": len(overview["projects"]) <= LIMITS.max_projects,
            "graph_nodes_bounded": len(graph["nodes"]) <= LIMITS.max_nodes,
            "graph_edges_bounded": len(graph["edges"]) <= LIMITS.max_edges,
            "changed_nodes_bounded": len(changed["nodes"]) <= LIMITS.max_nodes,
            "changed_edges_bounded": len(changed["edges"]) <= LIMITS.max_edges,
            "read_only": overview["read_only"] is True and graph["read_only"] is True,
            "secret_redacted": (
                "sk-proj-abcdefghijklmnop123456789" not in serialized
                and "[REDACTED:openai_key]" in serialized
            ),
            "no_absolute_repo_path": "/private/evaluation" not in serialized,
            "no_full_body_fields": all(
                forbidden not in serialized
                for forbidden in ('"details"', '"content"', '"signature"', '"body_sha256"')
            ),
            "changed_only_reduces_graph": len(changed["nodes"]) < len(graph["nodes"]),
            "changed_only_has_current_change": "logical-000" in changed_serialized,
            "overview_latency": overview_ms <= MAX_OVERVIEW_MS,
            "graph_latency": graph_ms <= MAX_GRAPH_MS,
            "changed_graph_latency": changed_ms <= MAX_GRAPH_MS,
        }
        return {
            "passed": all(checks.values()),
            "fixture": {
                "projects": PROJECT_COUNT,
                "focus_symbols": FOCUS_SYMBOLS,
                "focus_files": FOCUS_FILES,
                "focus_tasks": FOCUS_TASKS,
            },
            "limits": {
                "max_projects": LIMITS.max_projects,
                "max_nodes": LIMITS.max_nodes,
                "max_edges": LIMITS.max_edges,
                "max_records_per_kind": LIMITS.max_records_per_kind,
            },
            "observed": {
                "overview_projects": len(overview["projects"]),
                "graph_nodes": len(graph["nodes"]),
                "graph_edges": len(graph["edges"]),
                "changed_nodes": len(changed["nodes"]),
                "changed_edges": len(changed["edges"]),
                "overview_ms": round(overview_ms, 2),
                "graph_ms": round(graph_ms, 2),
                "changed_graph_ms": round(changed_ms, 2),
            },
            "thresholds_ms": {
                "overview": MAX_OVERVIEW_MS,
                "graph": MAX_GRAPH_MS,
            },
            "checks": checks,
        }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
