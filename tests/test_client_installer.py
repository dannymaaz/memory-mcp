from __future__ import annotations

import json
from pathlib import Path

from persistent_memory_mcp.client_installer import (
    SERVER_NAME,
    backup_config,
    detect_config_path,
    install_client_config,
    merge_codex_toml,
    merge_json_config,
    rollback_config,
)


def test_detect_config_paths(tmp_path: Path) -> None:
    assert detect_config_path("codex", home=tmp_path) == tmp_path / ".codex" / "config.toml"
    assert detect_config_path("claude", home=tmp_path) == tmp_path / ".claude.json"
    assert detect_config_path("opencode", home=tmp_path) == tmp_path / ".config" / "opencode" / "opencode.json"


def test_json_merge_preserves_unrelated_servers() -> None:
    current = {"mcpServers": {"other": {"command": "other"}}, "theme": "dark"}
    merged = merge_json_config("claude", current, {"command": "memory-mcp"})
    assert merged["mcpServers"]["other"]["command"] == "other"
    assert merged["mcpServers"][SERVER_NAME]["command"] == "memory-mcp"
    assert merged["theme"] == "dark"


def test_opencode_merge_preserves_schema() -> None:
    current = {"$schema": "https://opencode.ai/config.json", "mcp": {"other": {"enabled": True}}}
    merged = merge_json_config("opencode", current, {"type": "local", "command": ["memory-mcp"]})
    assert merged["$schema"] == current["$schema"]
    assert "other" in merged["mcp"]
    assert merged["mcp"][SERVER_NAME]["command"] == ["memory-mcp"]


def test_codex_merge_replaces_only_managed_block() -> None:
    current = "[model]\nname = \"gpt\"\n\n[mcp_servers.persistent-memory-mcp]\ncommand = \"old\"\n\n[other]\nvalue = 1\n"
    block = "[mcp_servers.persistent-memory-mcp]\ncommand = \"memory-mcp\""
    merged = merge_codex_toml(current, block)
    assert "command = \"old\"" not in merged
    assert "command = \"memory-mcp\"" in merged
    assert "[model]" in merged
    assert "[other]" in merged


def test_install_json_creates_backup_and_preserves_content(tmp_path: Path) -> None:
    path = tmp_path / "claude.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "other"}}}), encoding="utf-8")
    result = install_client_config("claude", {"command": "memory-mcp"}, config_path=path)
    assert result.backup_path is not None and result.backup_path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "other" in payload["mcpServers"]
    assert SERVER_NAME in payload["mcpServers"]


def test_backup_and_rollback(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("original", encoding="utf-8")
    backup = backup_config(path)
    assert backup is not None
    path.write_text("changed", encoding="utf-8")
    rollback_config(path, backup)
    assert path.read_text(encoding="utf-8") == "original"
