from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from persistent_memory_mcp.isolation import (
    IsolationError,
    assert_record_access,
    normalize_scope,
    owner_project_filters,
    secure_payload,
)
from persistent_memory_mcp.retention import (
    build_forget_plan,
    is_expired,
    select_retention_candidates,
)


def test_scope_requires_owner() -> None:
    with pytest.raises(ValueError):
        normalize_scope("")


def test_record_access_rejects_cross_owner() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    with pytest.raises(IsolationError):
        assert_record_access(
            {"id": "decision-1", "owner_id": "owner-b", "project_id": "project-1"},
            scope,
        )


def test_record_access_rejects_cross_project() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    with pytest.raises(IsolationError):
        assert_record_access(
            {"id": "decision-1", "owner_id": "owner-a", "project_id": "project-2"},
            scope,
        )


def test_secure_payload_attaches_scope() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    payload = secure_payload({"summary": "Use SQLite locally"}, scope)
    assert payload["owner_id"] == "owner-a"
    assert payload["project_id"] == "project-1"
    assert owner_project_filters(scope) == {
        "owner_id": "owner-a",
        "project_id": "project-1",
    }


def test_secure_payload_rejects_conflicting_owner() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    with pytest.raises(IsolationError):
        secure_payload({"owner_id": "owner-b"}, scope)


def test_expiry_reads_top_level_or_security_metadata() -> None:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    assert is_expired({"expires_at": (now - timedelta(seconds=1)).isoformat()}, now=now)
    assert is_expired(
        {
            "metadata": {
                "security": {"expires_at": (now - timedelta(days=1)).isoformat()}
            }
        },
        now=now,
    )
    assert not is_expired({}, now=now)


def test_retention_preserves_recent_records_and_selects_old() -> None:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    scope = normalize_scope("owner-a", project_id="project-1")
    records = [
        {
            "id": "new",
            "owner_id": "owner-a",
            "project_id": "project-1",
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "id": "old",
            "owner_id": "owner-a",
            "project_id": "project-1",
            "created_at": (now - timedelta(days=90)).isoformat(),
        },
    ]
    candidates = select_retention_candidates(
        records,
        scope,
        archive_after_days=30,
        keep_recent=1,
        now=now,
    )
    assert [row["id"] for row in candidates] == ["old"]


def test_retention_rejects_cross_owner_rows() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    with pytest.raises(IsolationError):
        select_retention_candidates(
            [
                {
                    "id": "foreign",
                    "owner_id": "owner-b",
                    "project_id": "project-1",
                    "created_at": "2020-01-01T00:00:00+00:00",
                }
            ],
            scope,
        )


def test_forget_plan_is_dry_run_and_deduplicated() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    record = {"id": "decision-1", "owner_id": "owner-a", "project_id": "project-1"}
    plan = build_forget_plan("decisions", [record, record], scope)
    assert plan.dry_run is True
    assert plan.record_ids == ("decision-1",)
    assert plan.count == 1


def test_forget_plan_rejects_unknown_table() -> None:
    scope = normalize_scope("owner-a", project_id="project-1")
    with pytest.raises(ValueError):
        build_forget_plan("users", [], scope)
