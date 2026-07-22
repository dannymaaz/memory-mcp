"""Database client helpers for local SQLite and remote Supabase backends."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from persistent_memory_mcp.storage import create_sqlite_client, normalize_backend

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - fallback for environments without dependency
    Client = Any  # type: ignore[misc,assignment]

    def create_client(url: str, key: str) -> Any:
        raise RuntimeError("supabase package is required to create the remote client")


load_dotenv()


def get_supabase_client() -> Any:
    """Create the configured storage client.

    The historical function name is preserved for compatibility with the existing
    service layer. For ``MEMORY_BACKEND=sqlite`` it returns a local facade exposing
    the subset of the Supabase query API used by ``src.server``.
    """

    backend = normalize_backend(os.getenv("MEMORY_BACKEND", "supabase"))
    if backend == "sqlite":
        return create_sqlite_client(os.getenv("SQLITE_PATH"))

    if backend == "postgresql" and not os.getenv("DATABASE_URL", "").strip():
        raise EnvironmentError("DATABASE_URL must be configured for postgresql backend")

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be configured")
    return create_client(supabase_url, supabase_key)


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
