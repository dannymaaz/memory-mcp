from __future__ import annotations

from persistent_memory_mcp.project_guardrails import (
    compact_guardrails,
    sanitize_credential_reference,
    validate_deployment_target,
)


def _manifest() -> dict[str, object]:
    return {
        "project": {
            "project_id": "recorder",
            "name": "Recorder",
            "repository": "dannymaaz/recorder",
            "production_environment": "ovh-canada",
        },
        "services": [
            {
                "service_id": "upload-notifier",
                "purpose": "Notify uploads",
                "deployment_target": "ovh-canada",
                "restart_command": "systemctl restart upload-notifier",
                "status": "production",
            },
            {
                "service_id": "recorder-bot",
                "deployment_target": "ovh-canada",
                "restart_command": "systemctl restart recorder-bot",
                "status": "production",
            },
        ],
        "critical_rules": ["Never restart recorder-bot for notifier changes"],
        "credential_references": [
            {
                "type": "ssh",
                "path_variable": "OVH_SSH_KEY_PATH",
                "host_variable": "OVH_HOST",
                "private_key": "__REDACTED__",
            }
        ],
    }


def test_secret_values_are_never_retained() -> None:
    cleaned = sanitize_credential_reference(
        {"type": "ssh", "path_variable": "SSH_KEY_PATH", "token": "__REDACTED__"}
    )
    assert "token" not in cleaned
    assert cleaned["path_variable"] == "SSH_KEY_PATH"
    assert cleaned["secret_value_stored"] is False


def test_compact_guardrails_keep_service_identity_and_rules() -> None:
    compact = compact_guardrails(_manifest())
    assert compact["project"]["project_id"] == "recorder"
    assert compact["services"][0]["service_id"] == "upload-notifier"
    assert compact["critical_rules"]
    assert "private_key" not in compact["credential_references"][0]


def test_valid_deployment_resolves_exact_service() -> None:
    result = validate_deployment_target(
        _manifest(),
        {
            "project_id": "recorder",
            "repository": "dannymaaz/recorder",
            "service_id": "upload-notifier",
            "deployment_target": "ovh-canada",
            "working_tree_clean": True,
            "tests_passed": True,
            "commit_sha": "abc123",
        },
    )
    assert result.allowed is True
    assert result.resolved["service"]["restart_command"] == "systemctl restart upload-notifier"


def test_wrong_bot_or_target_is_blocked() -> None:
    result = validate_deployment_target(
        _manifest(),
        {
            "project_id": "recorder",
            "repository": "dannymaaz/other",
            "service_id": "missing-bot",
            "deployment_target": "other-vps",
            "working_tree_clean": False,
            "tests_passed": False,
        },
    )
    assert result.allowed is False
    assert len(result.errors) >= 4
