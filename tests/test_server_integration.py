from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from persistent_memory_mcp.hybrid_search import local_embedding
from persistent_memory_mcp.server_integration import install_hybrid_search

PROJECT_ID = "123e4567-e89b-12d3-a456-426614174000"


class FakeServerModule:
    def __init__(self) -> None:
        self.server = SimpleNamespace(_tools={"search_semantic_memory": lambda **_kwargs: {}})
        self.rows = [
            {
                "id": "auth",
                "project_id": PROJECT_ID,
                "source_type": "decision",
                "title": "Fix authentication RLS",
                "content": "Resolve Supabase row level security policies.",
                "embedding": local_embedding("Fix authentication RLS Resolve Supabase row level security policies."),
            },
            {
                "id": "docs",
                "project_id": PROJECT_ID,
                "source_type": "checkpoint",
                "title": "Update README",
                "content": "Document installation instructions.",
                "embedding": local_embedding("Update README Document installation instructions."),
            },
        ]

    def _client(self, _owner_id: str | None = None) -> object:
        return object()

    def _resolve_or_create_project(self, *_args: Any, **_kwargs: Any) -> tuple[dict[str, str], None, None]:
        return {"id": PROJECT_ID}, None, None

    def _table_select(self, _client: object, _table: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return [row for row in self.rows if row["project_id"] == filters["project_id"]]


def test_install_replaces_direct_and_registered_tool() -> None:
    module = FakeServerModule()
    tool = install_hybrid_search(module)
    assert module.search_semantic_memory is tool
    assert module.server._tools["search_semantic_memory"] is tool


def test_integrated_search_returns_hybrid_scores_and_metrics() -> None:
    module = FakeServerModule()
    tool = install_hybrid_search(module)
    result = tool(
        query="authentication rls",
        project_id=PROJECT_ID,
        owner_id="demo-owner",
    )
    assert result["status"] == "ok"
    assert result["search_mode"] == "hybrid"
    assert result["matches"][0]["id"] == "auth"
    assert "hybrid_score" in result["matches"][0]
    assert result["metrics"]["embedding_calls"] == 1


def test_integrated_search_filters_source_types() -> None:
    module = FakeServerModule()
    tool = install_hybrid_search(module)
    result = tool(
        query="installation documentation",
        project_id=PROJECT_ID,
        source_types=["checkpoint"],
    )
    assert result["match_count"] == 1
    assert result["matches"][0]["id"] == "docs"


def test_query_embedding_avoids_provider_query_call() -> None:
    module = FakeServerModule()
    tool = install_hybrid_search(module)
    result = tool(
        query="authentication",
        project_id=PROJECT_ID,
        query_embedding=local_embedding("authentication"),
    )
    assert result["status"] == "ok"
    assert result["metrics"]["embedding_calls"] == 0


def test_invalid_limit_returns_structured_error() -> None:
    module = FakeServerModule()
    tool = install_hybrid_search(module)
    result = tool(query="authentication", project_id=PROJECT_ID, limit=0)
    assert result["tool"] == "search_semantic_memory"
    assert "limit" in result["error"]
