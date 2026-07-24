from __future__ import annotations

import pytest

from persistent_memory_mcp.knowledge_graph import (
    build_knowledge_graph,
    compact_graph_context,
    focus_subgraph,
)


def _tables() -> dict[str, list[dict[str, object]]]:
    return {
        "projects": [{"id": "p1", "name": "Memory MCP", "slug": "memory-mcp"}],
        "file_memory": [
            {
                "id": "f1",
                "project_id": "p1",
                "file_path": "src/server.py",
                "symbols": ["build_handler", {"qualified_name": "DashboardConfig.validate"}],
            },
            {"id": "f2", "project_id": "p1", "file_path": "tests/test_server.py"},
        ],
        "decisions": [
            {"id": "d1", "project_id": "p1", "title": "Use SQLite", "verification_status": "stale"}
        ],
        "tasks": [{"id": "t1", "project_id": "p1", "title": "Add graph view", "status": "pending"}],
        "warnings": [{"id": "w1", "project_id": "p1", "title": "Check migration"}],
        "sessions": [{"id": "s1", "project_id": "p1", "session_id": "session-1"}],
        "file_relations": [
            {
                "project_id": "p1",
                "source_file": "src/server.py",
                "target_file": "tests/test_server.py",
                "relation_type": "tested_by",
                "confidence": 0.9,
            }
        ],
    }


def test_build_graph_creates_typed_nodes_and_edges() -> None:
    graph = build_knowledge_graph(_tables(), project_id="p1")
    kinds = {node["kind"] for node in graph["nodes"]}
    relations = {edge["relation"] for edge in graph["edges"]}
    assert {"project", "file", "symbol", "decision", "task", "warning", "session"} <= kinds
    assert "contains" in relations
    assert "defines" in relations
    assert "tested_by" in relations
    stale = next(node for node in graph["nodes"] if node["id"] == "decisions:d1")
    assert stale["stale"] is True
    assert stale["contradicted"] is False


def test_build_graph_is_deterministic_and_bounded() -> None:
    tables = _tables()
    first = build_knowledge_graph(tables, max_nodes=3, max_edges=2)
    second = build_knowledge_graph(tables, max_nodes=3, max_edges=2)
    assert first == second
    assert len(first["nodes"]) == 3
    assert len(first["edges"]) <= 2
    assert first["truncated"] is True


def test_query_filters_entities_but_keeps_project_context() -> None:
    graph = build_knowledge_graph(_tables(), query="graph view")
    ids = {node["id"] for node in graph["nodes"]}
    assert "projects:p1" in ids
    assert "tasks:t1" in ids
    assert "warnings:w1" not in ids


def test_orphan_nodes_are_marked() -> None:
    tables = _tables()
    tables["tasks"].append({"id": "t2", "title": "Unscoped task"})
    graph = build_knowledge_graph(tables)
    orphan = next(node for node in graph["nodes"] if node["id"] == "tasks:t2")
    assert orphan["orphan"] is True


def test_focus_subgraph_returns_bounded_neighborhood() -> None:
    graph = build_knowledge_graph(_tables())
    focused = focus_subgraph(graph, ["file_memory:f1"], depth=1)
    ids = {node["id"] for node in focused["nodes"]}
    assert "file_memory:f1" in ids
    assert "projects:p1" in ids
    assert "file_memory:f2" in ids
    assert any(node_id.startswith("symbol:file_memory:f1") for node_id in ids)
    assert focused["selection"] == ["file_memory:f1"]


def test_compact_context_is_bounded_and_read_only() -> None:
    graph = build_knowledge_graph(_tables())
    context = compact_graph_context(graph, ["file_memory:f1"], depth=1, max_chars=120)
    assert context["read_only"] is True
    assert context["selection"] == ["file_memory:f1"]
    assert context["context"]
    assert len(context["context"]) <= 120


def test_graph_limits_are_validated() -> None:
    with pytest.raises(ValueError, match="max_nodes"):
        build_knowledge_graph({}, max_nodes=0)
    with pytest.raises(ValueError, match="depth"):
        focus_subgraph({"nodes": [], "edges": []}, [], depth=5)
    with pytest.raises(ValueError, match="max_chars"):
        compact_graph_context({"nodes": [], "edges": []}, [], max_chars=0)
