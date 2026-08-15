from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from persistent_memory_mcp.settings import RuntimeSettings


def test_empty_environment_defaults_to_local_sqlite() -> None:
    settings = RuntimeSettings.from_env({})

    assert settings.backend == "sqlite"
    assert settings.sqlite_path == Path.home() / ".memory-mcp" / "memory.db"
    assert settings.redact_secrets is True
    assert settings.default_retention_days == 90


def test_canonical_backend_wins_when_legacy_alias_matches() -> None:
    with pytest.warns(FutureWarning, match="MEMORY_STORAGE_BACKEND is deprecated"):
        settings = RuntimeSettings.from_env(
            {"MEMORY_BACKEND": "sqlite", "MEMORY_STORAGE_BACKEND": "local"}
        )

    assert settings.backend == "sqlite"


def test_legacy_backend_alias_is_temporarily_supported() -> None:
    with pytest.warns(FutureWarning, match="MEMORY_STORAGE_BACKEND is deprecated"):
        settings = RuntimeSettings.from_env({"MEMORY_STORAGE_BACKEND": "sqlite"})

    assert settings.backend == "sqlite"


def test_conflicting_backend_aliases_fail_closed() -> None:
    with pytest.warns(FutureWarning, match="MEMORY_STORAGE_BACKEND is deprecated"):
        with pytest.raises(ValueError, match="conflicts"):
            RuntimeSettings.from_env(
                {"MEMORY_BACKEND": "sqlite", "MEMORY_STORAGE_BACKEND": "supabase"}
            )


def test_invalid_backend_is_rejected() -> None:
    with pytest.raises((ValueError, ValidationError)):
        RuntimeSettings.from_env({"MEMORY_BACKEND": "unknown-backend"})


def test_supabase_backend_requires_credentials_without_leaking_secret() -> None:
    secret = "super-secret-service-key"

    with pytest.raises(ValidationError) as error:
        RuntimeSettings.from_env(
            {"MEMORY_BACKEND": "supabase", "SUPABASE_KEY": secret}
        )

    assert secret not in str(error.value)


def test_postgresql_backend_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        RuntimeSettings.from_env({"MEMORY_BACKEND": "postgresql"})


def test_secrets_are_masked_in_model_representation() -> None:
    settings = RuntimeSettings.from_env(
        {
            "MEMORY_BACKEND": "supabase",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "private-key-value",
            "MEMORY_CONFIRMATION_SECRET": "confirmation-secret-value",
        }
    )

    rendered = repr(settings)
    assert "private-key-value" not in rendered
    assert "confirmation-secret-value" not in rendered
    assert settings.supabase_key is not None
    assert settings.supabase_key.get_secret_value() == "private-key-value"


def test_owner_id_remains_confirmation_secret_fallback() -> None:
    settings = RuntimeSettings.from_env({"OWNER_ID": "stable-owner"})

    assert settings.resolved_confirmation_secret is not None
    assert settings.resolved_confirmation_secret.get_secret_value() == "stable-owner"


def test_privacy_and_retention_values_are_validated() -> None:
    settings = RuntimeSettings.from_env(
        {
            "MEMORY_REDACT_SECRETS": "false",
            "MEMORY_IGNORE": ".env, private/** ,*.pem",
            "MEMORY_DEFAULT_RETENTION_DAYS": "365",
            "LOG_LEVEL": "debug",
        }
    )

    assert settings.redact_secrets is False
    assert settings.ignore_patterns == (".env", "private/**", "*.pem")
    assert settings.default_retention_days == 365
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    "environment",
    [
        {"MEMORY_REDACT_SECRETS": "sometimes"},
        {"MEMORY_DEFAULT_RETENTION_DAYS": "not-a-number"},
        {"MEMORY_DEFAULT_RETENTION_DAYS": "0"},
        {"LOG_LEVEL": "TRACE"},
    ],
)
def test_invalid_operational_settings_are_rejected(environment: dict[str, str]) -> None:
    with pytest.raises((ValueError, ValidationError)):
        RuntimeSettings.from_env(environment)
