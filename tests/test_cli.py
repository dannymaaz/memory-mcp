from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from persistent_memory_mcp.cli import (
    CLIENTS,
    _client_payload,
    _config_block,
    _normalize_clients,
    _read_env,
    _write_client_configs,
    _write_env,
    command_status,
)


VALUES = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_KEY": "anon-test",
    "OWNER_ID": "test-owner",
    "DATABASE_URL": "",
}


def test_env_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    _write_env(path, VALUES)
    loaded = _read_env(path)
    assert loaded["SUPABASE_URL"] == VALUES["SUPABASE_URL"]
    assert loaded["OWNER_ID"] == "test-owner"


def test_generated_config_uses_public_command() -> None:
    config = _config_block(VALUES)
    server = config["mcpServers"]["persistent-memory-mcp"]
    assert server["command"] == "memory-mcp"


def test_normalize_clients_supports_multiple_and_all() -> None:
    assert _normalize_clients("codex,claude") == ["codex", "claude"]
    assert _normalize_clients("all") == list(CLIENTS)
    assert _normalize_clients("codex,codex,opencode") == ["codex", "opencode"]


def test_normalize_clients_rejects_unknown_client() -> None:
    with pytest.raises(ValueError, match="Unknown client"):
        _normalize_clients("codex,unknown")


def test_all_client_payloads_use_memory_mcp_command() -> None:
    for client in CLIENTS:
        _filename, content = _client_payload(client, VALUES)
        assert "memory-mcp" in content
        assert "anon-test" in content


def test_write_client_configs_creates_selected_files(tmp_path: Path) -> None:
    written = _write_client_configs(tmp_path, ["codex", "opencode"], VALUES)
    assert set(written) == {"codex", "opencode"}
    assert (tmp_path / "codex-config.toml").exists()
    assert (tmp_path / "opencode.json").exists()
    assert not (tmp_path / "claude-server.json").exists()


def test_opencode_payload_uses_current_local_mcp_schema() -> None:
    _filename, content = _client_payload("opencode", VALUES)
    payload = json.loads(content)
    server = payload["mcp"]["persistent-memory-mcp"]
    assert server["type"] == "local"
    assert server["command"] == ["memory-mcp"]
    assert server["enabled"] is True


def test_status_is_safe(tmp_path: Path, capsys) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "SUPABASE_URL=https://example.supabase.co\n"
        "SUPABASE_KEY=secret-value\n"
        "OWNER_ID=test-owner\n",
        encoding="utf-8",
    )
    assert command_status(Namespace(env=str(path))) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["configured"] is True
    assert payload["supported_clients"] == list(CLIENTS)
    assert "secret-value" not in output
