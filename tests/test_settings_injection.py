from pathlib import Path

import pytest

from persistent_memory_mcp.settings import RuntimeSettings
from src.utils.db import get_supabase_client


def test_storage_client_uses_injected_sqlite_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("SQLITE_PATH", raising=False)
    settings = RuntimeSettings(backend="sqlite", sqlite_path=tmp_path / "injected.db")

    client = get_supabase_client(settings)

    assert client.backend_name == "sqlite"
    assert client.storage.path == (tmp_path / "injected.db").resolve()
