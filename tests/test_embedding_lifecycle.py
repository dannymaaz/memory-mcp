from __future__ import annotations

from types import SimpleNamespace

from persistent_memory_mcp.embedding_lifecycle import (
    embedding_is_current,
    install_embedding_lifecycle,
)
from persistent_memory_mcp.hybrid_search import content_fingerprint, render_memory_text


def test_embedding_is_current_detects_matching_fingerprint() -> None:
    row = {"title": "Auth", "content": "Use short-lived tokens", "embedding": [1.0, 0.0]}
    row["metadata"] = {
        "embedding_fingerprint": content_fingerprint(render_memory_text(row)),
        "embedding_provider": "local",
    }
    assert embedding_is_current(row, "local") is True
    row["content"] = "Changed content"
    assert embedding_is_current(row, "local") is False


def test_reindex_updates_stale_rows_and_skips_current_rows(monkeypatch) -> None:
    project = {"id": "project-1"}
    current = {"id": "a", "project_id": "project-1", "title": "Current", "content": "same"}
    current["embedding"] = [0.0] * 96
    current["metadata"] = {
        "embedding_fingerprint": content_fingerprint(render_memory_text(current)),
        "embedding_provider": "local",
    }
    stale = {"id": "b", "project_id": "project-1", "title": "Stale", "content": "new"}
    writes: list[dict[str, object]] = []

    server_module = SimpleNamespace(
        _client=lambda owner_id=None: object(),
        _resolve_or_create_project=lambda *args, **kwargs: (project, {}, {}),
        _table_select=lambda *args, **kwargs: [current, stale],
        _table_upsert=lambda client, table, payload: writes.append(payload) or payload,
        server=SimpleNamespace(_tools={}, tool=lambda **kwargs: (lambda fn: fn)),
    )
    monkeypatch.setenv("MEMORY_EMBEDDING_PROVIDER", "local")
    tool = install_embedding_lifecycle(server_module)
    result = tool(project_id="project-1")

    assert result["status"] == "ok"
    assert result["updated"] == 1
    assert result["skipped"] == 1
    assert len(writes) == 1
    assert writes[0]["metadata"]["embedding_fingerprint"] == content_fingerprint(
        render_memory_text(stale)
    )


def test_install_is_idempotent() -> None:
    server_module = SimpleNamespace(
        server=SimpleNamespace(_tools={}, tool=lambda **kwargs: (lambda fn: fn))
    )
    first = install_embedding_lifecycle(server_module)
    second = install_embedding_lifecycle(server_module)
    assert first is second
