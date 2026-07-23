from __future__ import annotations

from types import SimpleNamespace

from persistent_memory_mcp.duplicate_intelligence import (
    analyze_memory_relationship,
    find_memory_relationships,
    install_duplicate_intelligence,
)


def test_exact_duplicate_is_recommended_for_merge() -> None:
    left = {"id": "a", "title": "Deploy", "content": "Use port 8080"}
    right = {"id": "b", "title": "Deploy", "content": "Use port 8080"}

    result = analyze_memory_relationship(left, right)

    assert result.relationship == "exact_duplicate"
    assert result.recommendation == "merge"
    assert result.confidence == 1.0


def test_conflicting_numeric_thresholds_are_kept_for_review() -> None:
    left = {"title": "Disk policy", "content": "Stop recording at 20 GB free"}
    right = {"title": "Disk policy", "content": "Stop recording at 40 GB free"}

    result = analyze_memory_relationship(left, right, related_threshold=0.4)

    assert result.relationship == "contradiction"
    assert result.recommendation == "keep_both"
    assert "different numeric thresholds" in result.evidence


def test_opposing_negation_is_detected() -> None:
    left = {"title": "Uploads", "content": "Uploads are enabled during maintenance"}
    right = {"title": "Uploads", "content": "Uploads are not enabled during maintenance"}

    result = analyze_memory_relationship(left, right, related_threshold=0.4)

    assert result.relationship == "contradiction"
    assert "opposing negation" in result.evidence


def test_relationships_exclude_candidate_and_are_deterministic() -> None:
    candidate = {"id": "candidate", "title": "Auth", "content": "Use short lived tokens"}
    older = {
        "id": "older",
        "title": "Auth",
        "content": "Use short lived tokens",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    newer = {
        "id": "newer",
        "title": "Auth",
        "content": "Use short lived tokens",
        "updated_at": "2026-02-01T00:00:00Z",
    }

    matches = find_memory_relationships(candidate, [candidate, older, newer])

    assert [match["item"]["id"] for match in matches] == ["newer", "older"]
    assert all(match["item"]["id"] != "candidate" for match in matches)


def test_mcp_tool_persists_only_bounded_relationship_metadata() -> None:
    project = {"id": "project-1"}
    candidate = {
        "id": "candidate",
        "project_id": "project-1",
        "title": "Deploy",
        "content": "Use port 8080",
        "metadata": {"source": "test"},
    }
    duplicate = {
        "id": "duplicate",
        "project_id": "project-1",
        "title": "Deploy",
        "content": "Use port 8080",
    }
    writes: list[dict[str, object]] = []
    server_module = SimpleNamespace(
        _client=lambda owner_id=None: object(),
        _resolve_or_create_project=lambda *args, **kwargs: (project, {}, {}),
        _table_select=lambda *args, **kwargs: [candidate, duplicate],
        _table_upsert=lambda client, table, payload: writes.append(payload) or payload,
        server=SimpleNamespace(_tools={}, tool=lambda **kwargs: (lambda fn: fn)),
    )

    tool = install_duplicate_intelligence(server_module)
    result = tool(memory_id="candidate", project_id="project-1", persist=True)

    assert result["status"] == "ok"
    assert result["persisted"] is True
    assert len(result["matches"]) == 1
    assert len(writes) == 1
    assert writes[0]["content"] == "Use port 8080"
    assert writes[0]["metadata"]["source"] == "test"
    relationships = writes[0]["metadata"]["memory_relationships"]
    assert relationships[0]["memory_id"] == "duplicate"
    assert relationships[0]["recommendation"] == "merge"


def test_tool_does_not_write_without_explicit_persist() -> None:
    project = {"id": "project-1"}
    rows = [
        {"id": "a", "project_id": "project-1", "title": "One", "content": "same"},
        {"id": "b", "project_id": "project-1", "title": "One", "content": "same"},
    ]
    writes: list[dict[str, object]] = []
    server_module = SimpleNamespace(
        _client=lambda owner_id=None: object(),
        _resolve_or_create_project=lambda *args, **kwargs: (project, {}, {}),
        _table_select=lambda *args, **kwargs: rows,
        _table_upsert=lambda client, table, payload: writes.append(payload) or payload,
        server=SimpleNamespace(_tools={}, tool=lambda **kwargs: (lambda fn: fn)),
    )

    result = install_duplicate_intelligence(server_module)(
        memory_id="a",
        project_id="project-1",
    )

    assert result["status"] == "ok"
    assert result["persisted"] is False
    assert writes == []


def test_installation_is_idempotent() -> None:
    server_module = SimpleNamespace(
        server=SimpleNamespace(_tools={}, tool=lambda **kwargs: (lambda fn: fn))
    )

    first = install_duplicate_intelligence(server_module)
    second = install_duplicate_intelligence(server_module)

    assert first is second
