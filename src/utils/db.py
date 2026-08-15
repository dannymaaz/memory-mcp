"""Database client helpers for local SQLite and optional remote backends."""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv

from persistent_memory_mcp.settings import RuntimeSettings
from persistent_memory_mcp.storage import create_sqlite_client

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - fallback for environments without dependency
    Client = Any  # type: ignore[misc,assignment]

    def create_client(url: str, key: str) -> Any:
        raise RuntimeError("supabase package is required to create the remote client")


load_dotenv()


def _configured_settings() -> RuntimeSettings:
    """Resolve one validated runtime configuration after dotenv loading."""
    return RuntimeSettings.from_env()


def _configured_backend() -> str:
    """Return the validated canonical backend for compatibility with existing callers."""
    return _configured_settings().backend


def get_supabase_client(settings: RuntimeSettings | None = None) -> Any:
    """Create a storage client from one validated settings object.

    The historical function name is preserved for compatibility with the existing
    service layer. Callers may inject ``RuntimeSettings`` so runtime composition does
    not need to re-read environment variables. When omitted, settings are resolved
    once from the current environment for backwards compatibility.
    """

    active_settings = settings or _configured_settings()
    if active_settings.backend == "sqlite":
        return create_sqlite_client(active_settings.sqlite_path)

    if active_settings.backend == "postgresql":
        if active_settings.database_url is None:
            raise EnvironmentError("DATABASE_URL must be configured for postgresql backend")
        # The historical helper still returns the Supabase-compatible query facade.
        # Direct PostgreSQL storage is configured elsewhere; do not silently reinterpret
        # DATABASE_URL as Supabase credentials here.

    if not active_settings.supabase_url or active_settings.supabase_key is None:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be configured")
    return create_client(
        active_settings.supabase_url,
        active_settings.supabase_key.get_secret_value(),
    )


def set_owner_context(client: Any, owner_id: str) -> Any:
    """Attach owner context for RLS, SQLite scoping and traceability."""
    normalized_owner = str(owner_id).strip()
    if not normalized_owner:
        raise ValueError("owner_id is required")

    if hasattr(client, "options") and getattr(client.options, "headers", None) is not None:
        client.options.headers["X-Owner-Context"] = normalized_owner
    if hasattr(client, "postgrest") and hasattr(client.postgrest, "headers"):
        client.postgrest.headers["X-Owner-Context"] = normalized_owner
    setattr(client, "owner_id", normalized_owner)
    return client
