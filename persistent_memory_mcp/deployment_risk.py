"""Deployment provenance, commit comparison and risk-aware execution controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence


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
    *,
    environment: str = "",
    action: str = "",
    destructive: bool = False,
    irreversible: bool = False,
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
    if len(present) <= 1:
        state = "aligned" if present else "unknown"
    else:
        state = "drift"
    return {
        **values,
        "state": state,
        "matches": {
            "repository_vs_deployed": bool(repository_commit and repository_commit == deployed_commit),
            "repository_vs_remembered": bool(repository_commit and repository_commit == remembered_commit),
            "deployed_vs_remembered": bool(deployed_commit and deployed_commit == remembered_commit),
        },
    }


def build_deployment_tools(server_module: Any) -> tuple[Callable[..., dict[str, Any]], Callable[..., dict[str, Any]]]:
    """Build bounded MCP tools for recording and reading deployment provenance."""

    def record_deployment(
        project_id: str,
        service: str,
        environment: str,
        commit_sha: str,
        result: str,
        *,
        operator: str | None = None,
        tests: Sequence[str] | None = None,
        rollback_target: str | None = None,
        action: str = "deploy",
        destructive: bool = False,
        irreversible: bool = False,
        confirmed: bool = False,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
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
        if not all(value.strip() for value in (project_id, service, environment, commit_sha, result)):
            return {"error": "project_id, service, environment, commit_sha and result are required"}
        client = server_module._client(owner_id)
        project, _, _ = server_module._resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=False,
        )
        payload = {
            "project_id": project["id"],
            "service": service.strip(),
            "environment": environment.strip(),
            "commit_sha": commit_sha.strip(),
            "result": result.strip(),
            "operator": operator,
            "tests": list(tests or []),
            "rollback_target": rollback_target,
            "risk_level": assessment.level,
            "risk_reasons": list(assessment.reasons),
            "confirmation_recorded": confirmed,
        }
        saved = server_module._table_insert(client, "deployment_records", payload)
        return {"status": "recorded", "deployment": saved, "risk": asdict(assessment)}

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
