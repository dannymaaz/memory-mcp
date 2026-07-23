from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from persistent_memory_mcp.security_integration import install_security_boundaries


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "projects": [{"id": "project-1", "owner_id": "owner-a", "name": "Demo"}],
            "workspaces": [{"id": "workspace-1", "owner_id": "owner-a"}],
        }
        self.last_write: tuple[str, dict[str, Any]] | None = None

    def select(
        self,
        _client: Any,
        table: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        return [
            dict(row)
            for row in self.rows.get(table, [])
            if all(row.get(key) == value for key, value in filters.items())
        ]

    def insert(self, _client: Any, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_write = (table, dict(payload))
        return dict(payload)

    def upsert(self, _client: Any, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_write = (table, dict(payload))
        return dict(payload)


def make_server(store: FakeStore) -> SimpleNamespace:
    return SimpleNamespace(
        _table_select=store.select,
        _table_insert=store.insert,
        _table_upsert=store.upsert,
    )


def test_write_redacts_secrets_and_attaches_security_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = make_server(store)
    install_security_boundaries(server)

    result = server._table_insert(
        object(),
        "memory_documents",
        {
            "project_id": "project-1",
            "owner_id": "owner-a",
            "title": "Deployment token",
            "content": "token=super-secret-value",
            "metadata": {"source": "test"},
        },
    )

    assert "super-secret-value" not in result["content"]
    assert "[REDACTED:generic_secret]" in result["content"]
    assert result["metadata"]["source"] == "test"
    assert result["metadata"]["security"]["sanitized"] is True
    assert result["owner_id"] == "owner-a"


def test_cross_owner_reads_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = make_server(store)
    install_security_boundaries(server)

    with pytest.raises(PermissionError, match="Cross-owner"):
        server._table_select(object(), "projects", {"owner_id": "owner-b"})


def test_project_scoped_write_requires_owned_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = make_server(store)
    install_security_boundaries(server)

    with pytest.raises(PermissionError, match="active owner"):
        server._table_upsert(
            object(),
            "tasks",
            {
                "project_id": "project-other",
                "owner_id": "owner-a",
                "title": "Unsafe task",
            },
        )


def test_owner_is_injected_and_foreign_owner_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = make_server(store)
    install_security_boundaries(server)

    result = server._table_upsert(
        object(),
        "projects",
        {"name": "New project", "slug": "new-project"},
    )
    assert result["owner_id"] == "owner-a"

    with pytest.raises(PermissionError, match="Cross-owner"):
        server._table_upsert(
            object(),
            "projects",
            {"owner_id": "owner-b", "name": "Foreign", "slug": "foreign"},
        )


def test_installation_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = make_server(store)
    install_security_boundaries(server)
    first_select = server._table_select
    install_security_boundaries(server)
    assert server._table_select is first_select
