"""Validated runtime configuration with a bounded legacy compatibility path."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .storage import normalize_backend

_CANONICAL_BACKEND_ENV = "MEMORY_BACKEND"
_LEGACY_BACKEND_ENV = "MEMORY_STORAGE_BACKEND"
_DEFAULT_SQLITE_PATH = Path.home() / ".memory-mcp" / "memory.db"
_ALLOWED_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class RuntimeSettings(BaseModel):
    """One immutable, validated configuration contract for local and remote runtimes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "sqlite"
    sqlite_path: Path = _DEFAULT_SQLITE_PATH
    owner_id: str | None = None
    supabase_url: str | None = None
    supabase_key: SecretStr | None = None
    database_url: SecretStr | None = None
    confirmation_secret: SecretStr | None = None
    log_level: str = "INFO"
    project_memory_interface: str = "native"
    redact_secrets: bool = True
    ignore_patterns: tuple[str, ...] = (".env", "*.pem", "*.key", "secrets/**")
    default_retention_days: int = Field(default=90, ge=1, le=3650)

    @field_validator("backend", mode="before")
    @classmethod
    def _validate_backend(cls, value: object) -> str:
        raw = str(value or "sqlite").strip()
        if not raw:
            raw = "sqlite"
        return normalize_backend(raw)

    @field_validator("sqlite_path", mode="before")
    @classmethod
    def _expand_sqlite_path(cls, value: object) -> Path:
        raw = str(value or _DEFAULT_SQLITE_PATH).strip()
        if not raw:
            raw = str(_DEFAULT_SQLITE_PATH)
        return Path(raw).expanduser()

    @field_validator("owner_id", "supabase_url", "project_memory_interface", mode="before")
    @classmethod
    def _empty_text_to_none_or_default(cls, value: object, info: object) -> object:
        if value is None:
            return value
        text = str(value).strip()
        if text:
            return text
        if getattr(info, "field_name", "") == "project_memory_interface":
            return "native"
        return None

    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, value: object) -> str:
        level = str(value or "INFO").strip().upper()
        if level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return level

    @model_validator(mode="after")
    def _validate_remote_backend_requirements(self) -> "RuntimeSettings":
        if self.backend == "supabase" and (not self.supabase_url or self.supabase_key is None):
            raise ValueError("supabase backend requires SUPABASE_URL and SUPABASE_KEY")
        if self.backend == "postgresql" and self.database_url is None:
            raise ValueError("postgresql backend requires DATABASE_URL")
        return self

    @property
    def resolved_confirmation_secret(self) -> SecretStr | None:
        """Return the explicit confirmation secret or the historical OWNER_ID fallback."""
        if self.confirmation_secret is not None:
            return self.confirmation_secret
        if self.owner_id:
            return SecretStr(self.owner_id)
        return None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "RuntimeSettings":
        """Build settings from environment variables without mutating process state."""
        source: Mapping[str, str] = os.environ if environ is None else environ
        canonical_raw = source.get(_CANONICAL_BACKEND_ENV)
        legacy_raw = source.get(_LEGACY_BACKEND_ENV)
        backend = cls._resolve_backend_aliases(canonical_raw, legacy_raw)

        return cls(
            backend=backend,
            sqlite_path=source.get("SQLITE_PATH") or _DEFAULT_SQLITE_PATH,
            owner_id=source.get("OWNER_ID"),
            supabase_url=source.get("SUPABASE_URL"),
            supabase_key=cls._optional_secret(source.get("SUPABASE_KEY")),
            database_url=cls._optional_secret(source.get("DATABASE_URL")),
            confirmation_secret=cls._optional_secret(source.get("MEMORY_CONFIRMATION_SECRET")),
            log_level=source.get("LOG_LEVEL") or "INFO",
            project_memory_interface=source.get("PROJECT_MEMORY_INTERFACE") or "native",
            redact_secrets=cls._parse_bool(source.get("MEMORY_REDACT_SECRETS"), default=True),
            ignore_patterns=cls._parse_csv(
                source.get("MEMORY_IGNORE"),
                default=(".env", "*.pem", "*.key", "secrets/**"),
            ),
            default_retention_days=cls._parse_int(
                source.get("MEMORY_DEFAULT_RETENTION_DAYS"),
                default=90,
                name="MEMORY_DEFAULT_RETENTION_DAYS",
            ),
        )

    @classmethod
    def _resolve_backend_aliases(cls, canonical: str | None, legacy: str | None) -> str:
        canonical_text = canonical.strip() if canonical is not None else ""
        legacy_text = legacy.strip() if legacy is not None else ""

        canonical_backend = normalize_backend(canonical_text) if canonical_text else None
        legacy_backend = normalize_backend(legacy_text) if legacy_text else None

        if legacy_backend is not None:
            warnings.warn(
                "MEMORY_STORAGE_BACKEND is deprecated; use MEMORY_BACKEND instead",
                FutureWarning,
                stacklevel=3,
            )
        if canonical_backend is not None and legacy_backend is not None:
            if canonical_backend != legacy_backend:
                raise ValueError(
                    "MEMORY_BACKEND conflicts with deprecated MEMORY_STORAGE_BACKEND; "
                    "remove the legacy alias or make both values match"
                )
            return canonical_backend
        return canonical_backend or legacy_backend or "sqlite"

    @staticmethod
    def _optional_secret(value: str | None) -> SecretStr | None:
        text = value.strip() if value is not None else ""
        return SecretStr(text) if text else None

    @staticmethod
    def _parse_bool(value: str | None, *, default: bool) -> bool:
        if value is None or not value.strip():
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError("MEMORY_REDACT_SECRETS must be a boolean value")

    @staticmethod
    def _parse_csv(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
        if value is None or not value.strip():
            return default
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @staticmethod
    def _parse_int(value: str | None, *, default: int, name: str) -> int:
        if value is None or not value.strip():
            return default
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
