from __future__ import annotations

import json

import pytest

from persistent_memory_mcp.operational_map import OperationalMapLimits, OperationalMapService
from persistent_memory_mcp.storage import SQLiteStorage


def _seed_project(storage: SQLiteStorage, owner_id: str, slug: str) -> dict[str, object]:
    workspaces = storage.select("workspaces", {"owner_id": owner_id})
    if workspaces:
        workspace = workspaces[0]
    else:
        workspace = storage.insert(
            "workspaces",
            {"owner_id": owner_id, "name": f"{owner_id} workspace", "slug": f"{owner_id}-workspace"},
        )
    return storage.insert(
        "projects",
        {
            "workspace_id": workspace["id"],
            "owner_id": owner_id,
            "name": f"Project {slug}",
            "slug": slug,
            "repo_path": f"/private/{owner_id}/{slug}",
            "repo_remote": f"https://example.invalid/{owner_id}/{slug}.git",
            "repo_branch": "main",
            "repo_last_commit": "b" * 40,
            "repo_status": {"dirty": False},
        },
    )


def _insert_run(
    storage: SQLiteStorage,
    *,
    owner_id: str,
    project_id: str,
    run_id: str,
    repository: str,
    commit: str,
    captured_at: str,
) -> None:
    storage.insert(
        "code_symbol_snapshot_runs",
        {
            "id": run_id,
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "commit_sha": commit,
            "ref": "main",
            "symbol_count": 2,
            "captured_at": captured_at,
        },
    )


def _insert_snapshot(
    storage: SQLiteStorage,
    *,
    owner_id: str,
    project_id: str,
    run_id: str,
    repository: str,
    commit: str,
    logical_id: str,
    name: str,
    path: str,
    state: str = "verified",
) -> None:
    storage.insert(
        "code_symbol_snapshots",
        {
            "id": f"snapshot-{run_id}-{logical_id}",
            "run_id": run_id,
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "commit_sha": commit,
            "ref": "main",
            "logical_id": logical_id,
            "source_symbol_id": f"source-{run_id}-{logical_id}",
            "path": path,
            "name": name,
            "qualified_name": name,
            "kind": "function",
            "language": "python",
            "line": 1,
            "end_line": 3,
            "signature": f"def {name}():",
            "signature_sha256": "1" * 64,
            "body_sha256": "2" * 64,
            "file_sha256": "3" * 64,
            "first_seen_commit": commit,
            "verification_state": state,
        },
    )


def _seed_operational_fixture(tmp_path):
    storage = SQLiteStorage(tmp_path / "memory.db")
    storage.initialize()
    owner_id = "owner-1"
    project = _seed_project(storage, owner_id, "alpha")
    foreign = _seed_project(storage, "owner-2", "foreign")
    project_id = str(project["id"])
    repository = str(project["repo_path"])

    linked_task = storage.insert(
        "tasks",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "title": "Rotate token sk-proj-abcdefghijklmnop123456789",
            "status": "blocked",
            "priority": "high",
        },
    )
    unrelated_task = storage.insert(
        "tasks",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "title": "Unrelated backlog task",
            "status": "pending",
            "priority": "low",
        },
    )
    decision = storage.insert(
        "decisions",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "summary": "Keep operational graphs bounded",
            "decision_type": "architecture",
        },
    )
    storage.insert(
        "warnings",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "message": "Contradicted source evidence needs review",
            "severity": "high",
            "is_active": True,
        },
    )
    storage.insert(
        "tasks",
        {
            "owner_id": "owner-2",
            "project_id": str(foreign["id"]),
            "title": "Foreign owner secret task",
            "status": "blocked",
        },
    )

    _insert_run(
        storage,
        owner_id=owner_id,
        project_id=project_id,
        run_id="run-old",
        repository=repository,
        commit="a" * 40,
        captured_at="2026-08-15 10:00:00",
    )
    _insert_snapshot(
        storage,
        owner_id=owner_id,
        project_id=project_id,
        run_id="run-old",
        repository=repository,
        commit="a" * 40,
        logical_id="logical-changed",
        name="process_order",
        path="src/orders.py",
    )
    storage.insert(
        "code_symbol_changes",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "to_run_id": "run-old",
            "to_commit": "a" * 40,
            "logical_id": "logical-changed",
            "new_snapshot_id": "snapshot-run-old-logical-changed",
            "change_type": "added",
        },
    )

    _insert_run(
        storage,
        owner_id=owner_id,
        project_id=project_id,
        run_id="run-new",
        repository=repository,
        commit="b" * 40,
        captured_at="2026-08-15 11:00:00",
    )
    _insert_snapshot(
        storage,
        owner_id=owner_id,
        project_id=project_id,
        run_id="run-new",
        repository=repository,
        commit="b" * 40,
        logical_id="logical-changed",
        name="process_order",
        path="src/orders.py",
    )
    _insert_snapshot(
        storage,
        owner_id=owner_id,
        project_id=project_id,
        run_id="run-new",
        repository=repository,
        commit="b" * 40,
        logical_id="logical-current-change",
        name="finalize_order",
        path="src/finalize.py",
    )
    storage.insert(
        "code_symbol_changes",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "from_run_id": "run-old",
            "to_run_id": "run-new",
            "from_commit": "a" * 40,
            "to_commit": "b" * 40,
            "logical_id": "logical-changed",
            "old_snapshot_id": "snapshot-run-old-logical-changed",
            "new_snapshot_id": "snapshot-run-new-logical-changed",
            "change_type": "unchanged",
        },
    )
    storage.insert(
        "code_symbol_changes",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "from_run_id": "run-old",
            "to_run_id": "run-new",
            "from_commit": "a" * 40,
            "to_commit": "b" * 40,
            "logical_id": "logical-current-change",
            "new_snapshot_id": "snapshot-run-new-logical-current-change",
            "change_type": "added",
        },
    )
    storage.insert(
        "code_symbol_links",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "logical_id": "logical-current-change",
            "snapshot_id": "snapshot-run-new-logical-current-change",
            "relation_type": "implements",
            "target_type": "task",
            "target_id": str(linked_task["id"]),
            "verification_state": "verified",
        },
    )
    storage.insert(
        "code_symbol_links",
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "repository": repository,
            "logical_id": "logical-current-change",
            "snapshot_id": "snapshot-run-new-logical-current-change",
            "relation_type": "informed_by",
            "target_type": "decision",
            "target_id": str(decision["id"]),
            "verification_state": "contradicted",
        },
    )
    return storage, owner_id, project, foreign, linked_task, unrelated_task


def test_operational_overview_is_owner_scoped_and_risk_aware(tmp_path) -> None:
    storage, owner_id, project, _, _, _ = _seed_operational_fixture(tmp_path)
    report = OperationalMapService(storage, owner_id=owner_id).project_overview()

    assert report["read_only"] is True
    assert report["counts"]["projects"] == 1
    assert [item["project_id"] for item in report["projects"]] == [str(project["id"])]
    assert report["projects"][0]["risk"] == "critical"
    assert report["projects"][0]["contradicted_evidence"] == 1
    assert report["projects"][0]["blocked_tasks"] == 1


def test_operational_map_rejects_cross_owner_project_access(tmp_path) -> None:
    storage, owner_id, _, foreign, _, _ = _seed_operational_fixture(tmp_path)
    service = OperationalMapService(storage, owner_id=owner_id)
    with pytest.raises(ValueError, match="owner scope"):
        service.impact_graph(str(foreign["id"]))


def test_operational_graph_is_bounded_redacted_and_body_free(tmp_path) -> None:
    storage, owner_id, project, _, linked_task, _ = _seed_operational_fixture(tmp_path)
    graph = OperationalMapService(storage, owner_id=owner_id).impact_graph(
        str(project["id"]), limits=OperationalMapLimits(max_nodes=8, max_edges=20, max_records_per_kind=10)
    )

    assert graph["read_only"] is True
    assert len(graph["nodes"]) <= 8
    assert len(graph["edges"]) <= 20
    serialized = json.dumps(graph, ensure_ascii=False)
    assert "sk-proj-abcdefghijklmnop123456789" not in serialized
    assert "[REDACTED:openai_key]" in serialized
    assert str(linked_task["id"]) in serialized
    for forbidden in ('"details"', '"content"', '"summary"', '"message"', '"signature"', '"body_sha256"'):
        assert forbidden not in serialized
    assert "/private/owner-1/alpha" not in serialized


def test_changed_only_uses_latest_run_and_keeps_only_affected_neighbors(tmp_path) -> None:
    storage, owner_id, project, _, linked_task, unrelated_task = _seed_operational_fixture(tmp_path)
    graph = OperationalMapService(storage, owner_id=owner_id).impact_graph(
        str(project["id"]), changed_only=True, limits=OperationalMapLimits(max_nodes=30, max_edges=60)
    )
    serialized = json.dumps(graph)

    # A symbol that changed only in an older run is not a current changed symbol.
    assert "logical-changed" not in serialized
    assert "logical-current-change" in serialized
    # Evidence directly linked to the changed symbol is retained, unrelated project work is not.
    assert str(linked_task["id"]) in serialized
    assert str(unrelated_task["id"]) not in serialized


def test_operational_filters_and_limits_fail_closed(tmp_path) -> None:
    storage, owner_id, project, _, _, _ = _seed_operational_fixture(tmp_path)
    service = OperationalMapService(storage, owner_id=owner_id)

    with pytest.raises(ValueError, match="verification"):
        service.project_overview(verification="maybe")
    with pytest.raises(ValueError, match="risk"):
        service.impact_graph(str(project["id"]), risk="urgent")
    with pytest.raises(ValueError, match="max_nodes"):
        OperationalMapLimits(max_nodes=501)
