"""Safe installation helpers for supported MCP clients."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

SERVER_NAME = "persistent-memory-mcp"
SUPPORTED_CLIENTS = ("codex", "claude", "opencode", "antigravity")


@dataclass(frozen=True)
class InstallResult:
    client: str
    config_path: Path
    backup_path: Path | None
    changed: bool


def detect_config_path(client: str, *, home: Path | None = None) -> Path:
    """Return the conventional user-level configuration path for a client."""

    root = (home or Path.home()).expanduser()
    normalized = client.strip().lower()
    mapping = {
        "codex": root / ".codex" / "config.toml",
        "claude": root / ".claude.json",
        "opencode": root / ".config" / "opencode" / "opencode.json",
        "antigravity": root / ".gemini" / "antigravity" / "mcp_config.json",
    }
    if normalized not in mapping:
        raise ValueError(f"Unsupported client: {client}")
    return mapping[normalized]


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def backup_config(path: Path) -> Path | None:
    """Create a timestamped backup beside an existing configuration file."""

    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.memory-mcp.{_timestamp()}.bak")
    shutil.copy2(path, backup)
    return backup


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON configuration must contain an object: {path}")
    return data


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json.loads(rendered)
    path.write_text(rendered, encoding="utf-8")


def merge_json_config(client: str, current: Mapping[str, Any], server: Mapping[str, Any]) -> dict[str, Any]:
    """Merge one server while preserving unrelated client configuration."""

    payload = dict(current)
    normalized = client.strip().lower()
    if normalized == "opencode":
        servers = dict(payload.get("mcp") or {})
        servers[SERVER_NAME] = dict(server)
        payload["mcp"] = servers
        return payload
    if normalized in {"claude", "antigravity"}:
        servers = dict(payload.get("mcpServers") or {})
        servers[SERVER_NAME] = dict(server)
        payload["mcpServers"] = servers
        return payload
    raise ValueError(f"JSON merge is not supported for client: {client}")


def merge_codex_toml(current: str, server_block: str) -> str:
    """Replace only the managed Codex block and preserve every unrelated section."""

    header = f"[mcp_servers.{SERVER_NAME}]"
    lines = current.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == header:
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("["):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    base = "\n".join(output).rstrip()
    block = server_block.strip()
    return f"{base}\n\n{block}\n" if base else f"{block}\n"


def install_client_config(
    client: str,
    server: Mapping[str, Any] | str,
    *,
    config_path: Path | None = None,
    home: Path | None = None,
) -> InstallResult:
    """Back up, merge, validate and atomically replace a client configuration."""

    normalized = client.strip().lower()
    path = config_path or detect_config_path(normalized, home=home)
    backup = backup_config(path)

    if normalized == "codex":
        if not isinstance(server, str):
            raise TypeError("Codex installation requires a TOML block string")
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        rendered = merge_codex_toml(current, server)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        os.replace(temp, path)
        return InstallResult(normalized, path, backup, rendered != current)

    if not isinstance(server, Mapping):
        raise TypeError("JSON client installation requires a mapping")
    current_json = _read_json(path)
    rendered_json = merge_json_config(normalized, current_json, server)
    changed = rendered_json != current_json
    temp = path.with_suffix(path.suffix + ".tmp")
    _write_json(temp, rendered_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp, path)
    return InstallResult(normalized, path, backup, changed)


def rollback_config(config_path: Path, backup_path: Path) -> None:
    """Restore a prior backup after validating both paths."""

    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError(str(backup_path))
    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, config_path)
