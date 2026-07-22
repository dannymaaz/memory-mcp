"""Project identity, service targeting and deployment safety guardrails."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SECRET_NAME_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|PRIVATE_KEY|API_KEY|SSH_KEY)$", re.IGNORECASE)
SECRET_VALUE_MARKERS = ("BEGIN OPENSSH PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "ssh-rsa ")


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    resolved: dict[str, Any]


def sanitize_credential_reference(reference: Mapping[str, Any]) -> dict[str, Any]:
    """Keep secret locations and variable names while rejecting secret material."""
    cleaned: dict[str, Any] = {}
    for key, value in reference.items():
        rendered = str(value)
        if key.lower() in {"value", "secret", "private_key", "password", "token"}:
            continue
        if any(marker in rendered for marker in SECRET_VALUE_MARKERS):
            continue
        if key.endswith("_variable") and not SECRET_NAME_RE.search(rendered):
            cleaned[key] = rendered
        elif key in {
            "type", "env_variable", "host_variable", "user_variable", "port_variable",
            "path_variable", "scope", "purpose", "secret_value_stored",
        }:
            cleaned[key] = value
    cleaned["secret_value_stored"] = False
    return cleaned


def compact_guardrails(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the small, always-loaded subset required for safe agent actions."""
    project = dict(manifest.get("project") or {})
    services = []
    for raw in manifest.get("services") or []:
        if not isinstance(raw, Mapping):
            continue
        services.append({
            key: raw.get(key)
            for key in (
                "service_id", "type", "purpose", "entrypoint", "deployment_target",
                "remote_directory", "restart_command", "status",
            )
            if raw.get(key) not in (None, "", [], {})
        })
    credentials = [
        sanitize_credential_reference(item)
        for item in manifest.get("credential_references") or []
        if isinstance(item, Mapping)
    ]
    return {
        "project": {
            key: project.get(key)
            for key in (
                "project_id", "name", "repository", "local_path", "primary_service",
                "production_environment", "deployment_method",
            )
            if project.get(key) not in (None, "", [], {})
        },
        "services": services,
        "critical_rules": [str(rule) for rule in manifest.get("critical_rules") or []],
        "agent_rules": [str(rule) for rule in manifest.get("agent_rules") or []],
        "credential_references": credentials,
    }


def _service_by_id(services: Sequence[Mapping[str, Any]], service_id: str) -> Mapping[str, Any] | None:
    for service in services:
        if str(service.get("service_id", "")) == service_id:
            return service
    return None


def validate_deployment_target(
    manifest: Mapping[str, Any],
    request: Mapping[str, Any],
) -> GuardrailResult:
    """Validate project, repository, service and deployment target before execution."""
    compact = compact_guardrails(manifest)
    project = compact["project"]
    services = compact["services"]
    errors: list[str] = []
    warnings: list[str] = []

    requested_project = str(request.get("project_id") or "")
    requested_repository = str(request.get("repository") or "")
    requested_service = str(request.get("service_id") or "")
    requested_target = str(request.get("deployment_target") or "")

    if requested_project and requested_project != str(project.get("project_id", "")):
        errors.append("project identity does not match the active project")
    if requested_repository and requested_repository != str(project.get("repository", "")):
        errors.append("repository does not match the active project")
    if not requested_service:
        errors.append("service_id is required for deployment actions")
        service = None
    else:
        service = _service_by_id(services, requested_service)
        if service is None:
            errors.append("service is not registered for this project")

    if service is not None:
        expected_target = str(service.get("deployment_target") or "")
        if requested_target and requested_target != expected_target:
            errors.append("deployment target does not match the registered service target")
        if str(service.get("status", "")).lower() in {"disabled", "retired"}:
            errors.append("service is not deployable")

    if request.get("working_tree_clean") is False:
        errors.append("working tree must be clean before deployment")
    if request.get("tests_passed") is False:
        errors.append("tests must pass before deployment")
    if not request.get("commit_sha"):
        warnings.append("deployment request has no commit SHA")

    resolved = {
        "project_id": project.get("project_id"),
        "repository": project.get("repository"),
        "service": dict(service) if service else None,
        "deployment_target": service.get("deployment_target") if service else None,
        "credential_references": compact["credential_references"],
        "critical_rules": compact["critical_rules"],
    }
    return GuardrailResult(not errors, tuple(errors), tuple(warnings), resolved)
