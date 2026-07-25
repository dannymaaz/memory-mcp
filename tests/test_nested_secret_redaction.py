from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from persistent_memory_mcp.security import redact_sensitive_value
from persistent_memory_mcp.security_integration import install_security_boundaries


class FakeStore:
    def __init__(self) -> None:
        self.rows = {
            "projects": [{"id": "project-1", "owner_id": "owner-a"}],
        }

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

    def insert(self, _client: Any, _table: str, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload)

    def upsert(self, _client: Any, _table: str, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload)


def test_recursive_redaction_preserves_container_shape() -> None:
    source = {
        "safe": "visible",
        "nested": {
            "items": [
                "token=super-secret-value",
                ("password=another-secret", 7),
            ]
        },
    }

    result = redact_sensitive_value(source)

    assert result.value["safe"] == "visible"
    assert isinstance(result.value["nested"]["items"], list)
    assert isinstance(result.value["nested"]["items"][1], tuple)
    assert "super-secret-value" not in str(result.value)
    assert "another-secret" not in str(result.value)
    assert result.redactions == ("generic_secret", "generic_secret")


def test_recursive_redaction_is_idempotent() -> None:
    first = redact_sensitive_value({"token": "token=super-secret-value"})
    second = redact_sensitive_value(first.value)

    assert second.value == first.value
    assert second.redactions == ()


def test_safe_values_remain_unchanged() -> None:
    source = {"count": 3, "enabled": True, "items": ["alpha", None]}

    result = redact_sensitive_value(source)

    assert result.value == source
    assert result.redactions == ()


def test_persistence_boundary_redacts_nested_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_ID", "owner-a")
    store = FakeStore()
    server = SimpleNamespace(
        _table_select=store.select,
        _table_insert=store.insert,
        _table_upsert=store.upsert,
    )
    install_security_boundaries(server)

    result = server._table_insert(
        object(),
        "memory_documents",
        {
            "project_id": "project-1",
            "content": "Safe content",
            "metadata": {
                "deployment": {
                    "credentials": ["api_key=abcdefghijklmnop"]
                }
            },
        },
    )

    serialized = str(result["metadata"])
    assert "abcdefghijklmnop" not in serialized
    assert "[REDACTED:generic_secret]" in serialized
    assert result["metadata"]["security"]["sanitized"] is True
    findings = result["metadata"]["security"]["findings"]
    assert findings[0]["redaction_types"] == ["generic_secret"]
