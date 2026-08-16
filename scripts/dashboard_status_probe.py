"""Temporary focused probe for DashboardStatusService diagnostics."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from persistent_memory_mcp.dashboard_status import DashboardStatusService
from persistent_memory_mcp.storage import SQLiteStorage

STAMP = "2026-08-16T05:00:00+00:00"


def build_result() -> tuple[dict[str, object], SQLiteStorage, Path]:
    root = Path(tempfile.mkdtemp(prefix="memory-mcp-dashboard-status-"))
    storage = SQLiteStorage(root / "memory.db")
    storage.initialize()
    storage.insert(
        "projects",
        {
            "id": "project-1",
            "owner_id": "owner-1",
            "name": "Dashboard status",
            "slug": "dashboard-status",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "tasks",
        {
            "id": "task-1",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "title": "Sensitive task",
            "status": "pending",
            "sensitivity": "restricted",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "decisions",
        {
            "id": "decision-1",
            "project_id": "project-1",
            "owner_id": "owner-1",
            "decision": "Keep local",
            "context": "Dashboard maintenance",
            "sensitivity": "internal",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    with storage.connect() as connection:
        connection.execute(
            "insert into code_symbol_links("
            "id, project_id, owner_id, repository, logical_id, relation_type, target_type, "
            "target_id, verification_state, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "link-1",
                "project-1",
                "owner-1",
                "github.com/example/repo",
                "symbol-1",
                "implemented_by",
                "task",
                "task-1",
                "stale",
                STAMP,
                STAMP,
            ),
        )
        connection.commit()
    result = DashboardStatusService(storage, owner_id="owner-1").read(project_id="project-1")
    return result, storage, root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=("health", "verification", "sensitivity", "paths"))
    args = parser.parse_args()
    result, storage, root = build_result()
    checks = {
        "health": (
            result["status"] == "healthy"
            and result["health"]["maintenance_ready"] is False
            and result["health"]["quick_check"] == ["ok"]
            and result["storage"]["database_size_bytes"] > 0
            and result["storage"]["disk_free_bytes"] > 0
        ),
        "verification": (
            result["verification"]["evidence_states"]["stale"] == 1
            and result["verification"]["evidence_risk_count"] == 1
        ),
        "sensitivity": result["sensitivity"]["totals"]
        == {"internal": 1, "restricted": 1},
        "paths": str(storage.path) not in str(result) and str(root) not in str(result),
    }
    print(json.dumps({"check": args.check, "passed": checks[args.check], "result": result}, default=str))
    if not checks[args.check]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
