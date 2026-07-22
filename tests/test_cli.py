from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from persistent_memory_mcp.cli import _config_block, _read_env, _write_env, command_status


def test_env_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "anon-test",
        "OWNER_ID": "test-owner",
        "DATABASE_URL": "",
    }
    _write_env(path, values)
    loaded = _read_env(path)
    assert loaded["SUPABASE_URL"] == values["SUPABASE_URL"]
    assert loaded["OWNER_ID"] == "test-owner"


def test_generated_config_uses_public_command() -> None:
    config = _config_block(
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-test",
            "OWNER_ID": "test-owner",
        }
    )
    server = config["mcpServers"]["persistent-memory-mcp"]
    assert server["command"] == "memory-mcp"


def test_status_is_safe(tmp_path: Path, capsys) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "SUPABASE_URL=https://example.supabase.co\nSUPABASE_KEY=secret-value\nOWNER_ID=test-owner\n",
        encoding="utf-8",
    )
    assert command_status(Namespace(env=str(path))) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["configured"] is True
    assert "secret-value" not in output
