"""Security controls for persistent memory ingestion and retention."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

DEFAULT_MAX_TEXT_LENGTH = 20_000
DEFAULT_TTL_DAYS = 365

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    ),
    (
        "openai_key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "github_token",
        re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "generic_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*([\"']?)[^\s,;\"']{8,}\2"
        ),
    ),
)

_INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(ignore|disregard|override)\b.{0,40}\b(instructions?|rules?|policy)\b"),
    re.compile(r"(?i)\b(system|developer)\s+(message|prompt)\b"),
    re.compile(r"(?i)\bexecute\b.{0,30}\b(command|shell|code)\b"),
)


@dataclass(frozen=True)
class SanitizedMemory:
    """Sanitized memory plus security metadata."""

    content: str
    redactions: tuple[str, ...]
    instruction_like: bool
    truncated: bool
    provenance: dict[str, str]
    expires_at: str


def _redact_secrets(value: str) -> tuple[str, tuple[str, ...]]:
    redactions: list[str] = []
    sanitized = value
    for label, pattern in _SECRET_PATTERNS:
        sanitized, count = pattern.subn(f"[REDACTED:{label}]", sanitized)
        if count:
            redactions.extend([label] * count)
    return sanitized, tuple(redactions)


def _looks_instruction_like(value: str) -> bool:
    return any(pattern.search(value) for pattern in _INSTRUCTION_PATTERNS)


def _normalize_provenance(provenance: Mapping[str, Any] | None) -> dict[str, str]:
    source = dict(provenance or {})
    allowed = ("interface", "model", "session_id", "source_type", "source_id")
    return {key: str(source[key])[:256] for key in allowed if source.get(key) is not None}


def sanitize_memory(
    content: str,
    *,
    provenance: Mapping[str, Any] | None = None,
    max_length: int = DEFAULT_MAX_TEXT_LENGTH,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: datetime | None = None,
) -> SanitizedMemory:
    """Redact secrets, cap size and attach safe provenance/retention metadata.

    Stored text is treated as untrusted data. ``instruction_like`` allows callers to
    keep it out of system/developer prompt positions when loading context.
    """

    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if max_length < 1:
        raise ValueError("max_length must be positive")
    if ttl_days < 1:
        raise ValueError("ttl_days must be positive")

    redacted, redactions = _redact_secrets(content)
    truncated = len(redacted) > max_length
    bounded = redacted[:max_length]
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    expires_at = current.astimezone(UTC) + timedelta(days=ttl_days)

    return SanitizedMemory(
        content=bounded,
        redactions=redactions,
        instruction_like=_looks_instruction_like(bounded),
        truncated=truncated,
        provenance=_normalize_provenance(provenance),
        expires_at=expires_at.isoformat(),
    )


def security_metadata(result: SanitizedMemory) -> dict[str, Any]:
    """Return JSON-compatible metadata for database writes."""

    return {
        "security": {
            "redacted": bool(result.redactions),
            "redaction_types": sorted(set(result.redactions)),
            "instruction_like": result.instruction_like,
            "truncated": result.truncated,
            "provenance": result.provenance,
            "expires_at": result.expires_at,
            "content_trusted": False,
        }
    }
