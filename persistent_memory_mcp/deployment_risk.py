"""Deployment provenance, commit comparison and risk-aware execution controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class RiskAssessment:
    level: str
    confirmation_required: bool
    reasons: tuple[str, ...]
    rollback_required: bool


_HIGH_RISK_TERMS = {
    "production",
    "prod",
    "delete",
    "drop",
    "destroy",
    "force",
    "reset",
    "rollback",
    "migrate",
}
_MEDIUM_RISK_TERMS = {"restart", "deploy", "release", "staging", "schema", "database"}


def assess_execution_risk(
    *, environment: str = "", action: str = "", destructive: bool = False, irreversible: bool = False
) -> RiskAssessment:
    """Classify an action using explicit, explainable signals."""
    text = f"{environment} {action}".lower()
    reasons: list[str] = []
    if destructive:
        reasons.append("destructive action")
    if irreversible:
        reasons.append("irreversible action")
    matched_high = sorted(term for term in _HIGH_RISK_TERMS if term in text)
    matched_medium = sorted(term for term in _MEDIUM_RISK_TERMS if term in text)
    if matched_high:
        reasons.append(f"high-risk terms: {', '.join(matched_high)}")
    if destructive or irreversible or matched_high:
        return RiskAssessment("high", True, tuple(reasons), True)
    if matched_medium:
        reasons.append(f"operational terms: {', '.join(matched_medium)}")
        return RiskAssessment("medium", False, tuple(reasons), True)
    return RiskAssessment("low", False, ("no elevated-risk signals",), False)


def validate_deployment_target(
    *, service: str, environment: str, host: str, directory: str, restart_command: str
) -> tuple[str, ...]:
    """Return missing or unsafe target fields without executing any command."""
    problems: list[str] = []
    for name, value in (
        ("service", service),
        ("environment", environment),
        ("host", host),
        ("directory", directory),
        ("restart_command", restart_command),
    ):
        if not value or not value.strip():
            problems.append(f"{name} is required")
    if directory and not directory.strip().startswith(("/", "~", ".")):
        problems.append("directory must be an explicit path")
    command = f" {restart_command.lower()} "
    if any(token in command for token in (" rm -rf ", ";rm ", "&& rm")):
        problems.append("restart_command contains a destructive shell sequence")
    return tuple(problems)


def detect_scope_drift(
    intended_service: str,
    intended_environment: str,
    actual_service: str,
    actual_environment: str,
) -> dict[str, Any]:
    """Detect intent-versus-target drift before recording execution."""
    mismatches: list[str] = []
    if intended_service.strip() != actual_service.strip():
        mismatches.append("service")
    if intended_environment.strip() != actual_environment.strip():
        mismatches.append("environment")
    return {"drift": bool(mismatches), "mismatches": mismatches}


def build_rollback_plan(
    *, service: str, environment: str, rollback_target: str | None, restart_command: str
) -> dict[str, Any]:
    """Build a non-executing rollback plan from explicit deployment provenance."""
    if not rollback_target:
        return {"available": False, "steps": [], "reason": "rollback_target is required"}
    return {
        "available": True,
        "steps": [
            f"Restore {service} in {environment} to {rollback_target}",
            f"Run validated restart command: {restart_command}",
            "Verify health checks and compare deployed commit",
        ],
    }


def compare_deployment_commits(
    repository_commit: str | None,
    deployed_commit: str | None,
    remembered_commit: str | None,
) -> dict[str, Any]:
    """Compare repository, deployed and remembered commits without guessing ancestry."""
    values = {
        "repository_commit": repository_commit,
        "deployed_commit": deployed_commit,
        "remembered_commit": remembered_commit,
    }
    present = {value for value in values.values() if value}
    state = "aligned" if len(present) == 1 else "drift" if len(present) > 1 else "unknown"
    return {
        **values,
        "state": state,
        "matches": {
            "repository_vs_deployed": bool(repository_commit and repository_commit == deployed_commit),
            "repository_vs_remembered": bool(repository_commit and repository_commit == remembered_commit),
            "deployed_vs_remembered": bool(deployed_commit and deployed_commit == remembered_commit),
        },
    }


def build_deployment_tools(
    server_module: Any,
) -> tuple[Callable[..., dict[str, Any]], Callable[..., dict[str, Any]]]:
    """Build bounded MCP tools for recording and reading deployment provenance."""

    def record_deployment(
        project_id: str,
        service: str,
        environment: str,
        commit_sha: str,
        result: str,
        *,
        host: str,
        directory: str,
        restart_command: str,
        intended_service: str | None = None,
        intended_environment: str | None = None,
        operator: str | None = None,
        tests: Sequence[str] | None = None,
        rollback_target: str | None = None,
        action: str = "deploy",
        destructive: bool = False,
        irreversible: bool = False,
        confirmed: bool = False,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        target_errors = validate_deployment_target(
            service=service,
            environment=environment,
            host=host,
            directory=directory,
            restart_command=restart_command,
        )
        if target_errors:
            return {"status": "invalid_target", "errors": list(target_errors)}
        drift = detect_scope_drift(
            intended_service or service,
            intended_environment or environment,
            service,
            environment,
        )
        if drift["drift"]:
            return {"status": "scope_drift", **drift}
        assessment = assess_execution_risk(
            environment=environment,
            action=action,
            destructive=destructive,
            irreversible=irreversible,
        )
        if assessment.confirmation_required and not confirmed:
            return {
                "status": "confirmation_required",
                "risk": asdict(assessment),
                "project_id": project_id,
                "service": service,
                "environment": environment,
                "commit_sha": commit_sha,
            }
        if assessment.rollback_required and not rollback_target:
            return {"status": "rollback_required", "risk": asdict(assessment)}
        if not all(value.strip() for value in (project_id, service, environment, commit_sha, result)):
            return {"error": "project_id, service, environment, commit_sha and result are required"}
        client = server_module._client(owner_id)
        project, _, _ = server_module._resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=False,
        )
        rollback_plan = build_rollback_plan(
            service=service,
            environment=environment,
            rollback_target=rollback_target,
            restart_command=restart_command,
        )
        payload = {
            "project_id": project["id"],
            "owner_id": project.get("owner_id") or owner_id,
            "service": service.strip(),
            "environment": environment.strip(),
            "host": host.strip(),
            "directory": directory.strip(),
            "restart_command": restart_command.strip(),
            "commit_sha": commit_sha.strip(),
            "result": result.strip(),
            "operator": operator,
            "tests": list(tests or []),
            "rollback_target": rollback_target,
            "rollback_plan": rollback_plan,
            "risk_level": assessment.level,
            "risk_reasons": list(assessment.reasons),
            "confirmation_recorded": confirmed,
        }
        saved = server_module._table_insert(client, "deployment_records", payload)
        return {
            "status": "recorded",
            "deployment": saved,
            "risk": asdict(assessment),
            "rollback_plan": rollback_plan,
        }

    def get_deployment_history(
        project_id: str,
        *,
        service: str | None = None,
        environment: str | None = None,
        limit: int = 50,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            return {"error": "limit must be between 1 and 500"}
        client = server_module._client(owner_id)
        project, _, _ = server_module._resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=False,
        )
        filters: dict[str, Any] = {"project_id": project["id"]}
        if service:
            filters["service"] = service
        if environment:
            filters["environment"] = environment
        rows = server_module._table_select(client, "deployment_records", filters)
        rows = sorted(
            rows,
            key=lambda row: str(row.get("created_at") or row.get("updated_at") or ""),
            reverse=True,
        )[:limit]
        return {"status": "ok", "project_id": project["id"], "deployments": rows}

    record_deployment.__name__ = "record_deployment"
    get_deployment_history.__name__ = "get_deployment_history"
    return record_deployment, get_deployment_history


def install_deployment_risk(server_module: Any) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Install deployment tools once without rewriting the legacy server."""
    if getattr(server_module, "_deployment_risk_installed", False):
        return server_module.record_deployment, server_module.get_deployment_history
    record, history = build_deployment_tools(server_module)
    server_module.record_deployment = record
    server_module.get_deployment_history = history
    for name, description, function in (
        ("record_deployment", "Registra despliegues con procedencia y controles de riesgo.", record),
        ("get_deployment_history", "Consulta historial acotado de despliegues.", history),
    ):
        try:
            server_module.server.tool(name=name, description=description)(function)
        except Exception:
            pass
    server_module._deployment_risk_installed = True
    return record, history
