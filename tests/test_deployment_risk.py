from __future__ import annotations

from types import SimpleNamespace

from persistent_memory_mcp.deployment_risk import (
    assess_execution_risk,
    build_rollback_plan,
    compare_deployment_commits,
    detect_scope_drift,
    install_deployment_risk,
    validate_deployment_target,
)
from persistent_memory_mcp.deployment_storage import install_deployment_storage


def _server_module(writes: list[dict[str, object]]) -> SimpleNamespace:
    project = {"id": "project-1", "owner_id": "owner-1"}
    rows = [
        {"id": "older", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "newer", "created_at": "2026-02-01T00:00:00Z"},
    ]
    return SimpleNamespace(
        _client=lambda owner_id=None: object(),
        _resolve_or_create_project=lambda *args, **kwargs: (project, {}, {}),
        _table_insert=lambda client, table, payload: writes.append(payload) or payload,
        _table_select=lambda client, table, filters: rows,
        server=SimpleNamespace(tool=lambda **kwargs: (lambda fn: fn)),
    )


def _record(record, **overrides):
    values = {
        "project_id": "project-1",
        "service": "api",
        "environment": "production",
        "commit_sha": "abc",
        "result": "success",
        "host": "api.example.com",
        "directory": "/srv/api",
        "restart_command": "systemctl restart api",
    }
    values.update(overrides)
    return record(**values)


def test_production_requires_confirmation() -> None:
    assessment = assess_execution_risk(environment="production", action="deploy")
    assert assessment.level == "high"
    assert assessment.confirmation_required is True
    assert assessment.rollback_required is True


def test_commit_comparison_detects_drift() -> None:
    result = compare_deployment_commits("abc", "def", "abc")
    assert result["state"] == "drift"
    assert result["matches"]["repository_vs_remembered"] is True


def test_target_validation_rejects_unsafe_command() -> None:
    errors = validate_deployment_target(
        service="api",
        environment="production",
        host="api.example.com",
        directory="/srv/api",
        restart_command="systemctl stop api && rm -rf /srv/api",
    )
    assert "restart_command contains a destructive shell sequence" in errors


def test_scope_drift_is_reported() -> None:
    result = detect_scope_drift("api", "production", "worker", "production")
    assert result == {"drift": True, "mismatches": ["service"]}


def test_rollback_plan_requires_target() -> None:
    result = build_rollback_plan(
        service="api",
        environment="production",
        rollback_target=None,
        restart_command="systemctl restart api",
    )
    assert result["available"] is False


def test_high_risk_record_does_not_write_without_confirmation() -> None:
    writes: list[dict[str, object]] = []
    record, _ = install_deployment_risk(_server_module(writes))
    result = _record(record)
    assert result["status"] == "confirmation_required"
    assert writes == []


def test_high_risk_record_requires_rollback_target_after_confirmation() -> None:
    writes: list[dict[str, object]] = []
    record, _ = install_deployment_risk(_server_module(writes))
    result = _record(record, confirmed=True)
    assert result["status"] == "rollback_required"
    assert writes == []


def test_confirmed_record_preserves_scope_and_provenance() -> None:
    writes: list[dict[str, object]] = []
    record, _ = install_deployment_risk(_server_module(writes))
    result = _record(
        record,
        confirmed=True,
        rollback_target="previous",
        tests=["pytest"],
    )
    assert result["status"] == "recorded"
    assert writes[0]["project_id"] == "project-1"
    assert writes[0]["owner_id"] == "owner-1"
    assert writes[0]["rollback_target"] == "previous"
    assert writes[0]["rollback_plan"]["available"] is True


def test_scope_drift_prevents_write() -> None:
    writes: list[dict[str, object]] = []
    record, _ = install_deployment_risk(_server_module(writes))
    result = _record(
        record,
        intended_service="worker",
        confirmed=True,
        rollback_target="previous",
    )
    assert result["status"] == "scope_drift"
    assert writes == []


def test_history_is_bounded_and_newest_first() -> None:
    writes: list[dict[str, object]] = []
    _, history = install_deployment_risk(_server_module(writes))
    result = history("project-1", limit=1)
    assert [row["id"] for row in result["deployments"]] == ["newer"]


def test_install_is_idempotent() -> None:
    module = _server_module([])
    first = install_deployment_risk(module)
    second = install_deployment_risk(module)
    assert first == second


def test_sqlite_storage_install_is_idempotent() -> None:
    install_deployment_storage()
    install_deployment_storage()
