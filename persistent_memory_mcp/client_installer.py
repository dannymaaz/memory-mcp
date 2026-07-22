"""Safe installation lifecycle for supported MCP clients."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tomllib
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
    manifest_path: Path


def _platform_name(platform: str | None = None) -> str:
    value = (platform or sys.platform).lower()
    if value.startswith("win"):
        return "windows"
    if value == "darwin":
        return "macos"
    return "linux"


def detect_config_path(
    client: str,
    *,
    home: Path | None = None,
    platform: str | None = None,
    appdata: Path | None = None,
) -> Path:
    """Return the conventional user-level configuration path for a client."""
    root = (home or Path.home()).expanduser()
    normalized = client.strip().lower()
    if normalized not in SUPPORTED_CLIENTS:
        raise ValueError(f"Unsupported client: {client}")
    system = _platform_name(platform)
    if system == "windows":
        roaming = appdata or Path(os.getenv("APPDATA", root / "AppData" / "Roaming"))
        mapping = {
            "codex": root / ".codex" / "config.toml",
            "claude": roaming / "Claude" / "claude_desktop_config.json",
            "opencode": roaming / "opencode" / "opencode.json",
            "antigravity": root / ".gemini" / "antigravity" / "mcp_config.json",
        }
    else:
        mapping = {
            "codex": root / ".codex" / "config.toml",
            "claude": root / ".claude.json",
            "opencode": root / ".config" / "opencode" / "opencode.json",
            "antigravity": root / ".gemini" / "antigravity" / "mcp_config.json",
        }
    return mapping[normalized]


def manifest_path(home: Path | None = None) -> Path:
    return (home or Path.home()).expanduser() / ".memory-mcp" / "client-installations.json"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def backup_config(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.memory-mcp.{_timestamp()}.bak")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.memory-mcp.{_timestamp()}.{counter}.bak")
        counter += 1
    shutil.copy2(path, backup)
    return backup


def list_backups(path: Path) -> list[Path]:
    if not path.parent.exists():
        return []
    pattern = f"{path.name}.memory-mcp.*.bak"
    return sorted(path.parent.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON configuration must contain an object: {path}")
    return data


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.memory-mcp.tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json.loads(rendered)
    _atomic_write(path, rendered)


def merge_json_config(client: str, current: Mapping[str, Any], server: Mapping[str, Any]) -> dict[str, Any]:
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


def remove_json_server(client: str, current: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(current)
    key = "mcp" if client == "opencode" else "mcpServers"
    servers = dict(payload.get(key) or {})
    servers.pop(SERVER_NAME, None)
    if servers:
        payload[key] = servers
    else:
        payload.pop(key, None)
    return payload


def merge_codex_toml(current: str, server_block: str) -> str:
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
    rendered = f"{base}\n\n{block}\n" if base else f"{block}\n"
    tomllib.loads(rendered)
    return rendered


def remove_codex_server(current: str) -> str:
    rendered = merge_codex_toml(current, "")
    if rendered.strip():
        tomllib.loads(rendered)
    return rendered


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except (ValueError, json.JSONDecodeError):
        return {}


def _record_manifest(path: Path, result: InstallResult) -> None:
    payload = _read_manifest(path)
    installations = dict(payload.get("installations") or {})
    installations[result.client] = {
        "config_path": str(result.config_path),
        "last_backup": str(result.backup_path) if result.backup_path else None,
        "installed_at": datetime.now(UTC).isoformat(),
    }
    payload["version"] = 1
    payload["installations"] = installations
    _write_json(path, payload)


def install_client_config(
    client: str,
    server: Mapping[str, Any] | str,
    *,
    config_path: Path | None = None,
    home: Path | None = None,
) -> InstallResult:
    normalized = client.strip().lower()
    path = config_path or detect_config_path(normalized, home=home)
    current_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if normalized == "codex":
        if not isinstance(server, str):
            raise TypeError("Codex installation requires a TOML block string")
        rendered = merge_codex_toml(current_text, server)
    else:
        if not isinstance(server, Mapping):
            raise TypeError("JSON client installation requires a mapping")
        current_json = _read_json(path)
        rendered_json = merge_json_config(normalized, current_json, server)
        rendered = json.dumps(rendered_json, indent=2, ensure_ascii=False) + "\n"
    changed = rendered != current_text
    backup = backup_config(path) if changed else None
    if changed:
        _atomic_write(path, rendered)
    mpath = manifest_path(home)
    result = InstallResult(normalized, path, backup, changed, mpath)
    _record_manifest(mpath, result)
    return result


def uninstall_client_config(
    client: str,
    *,
    config_path: Path | None = None,
    home: Path | None = None,
) -> InstallResult:
    normalized = client.strip().lower()
    path = config_path or detect_config_path(normalized, home=home)
    if not path.exists():
        return InstallResult(normalized, path, None, False, manifest_path(home))
    current = path.read_text(encoding="utf-8")
    if normalized == "codex":
        rendered = remove_codex_server(current)
    else:
        rendered_json = remove_json_server(normalized, _read_json(path))
        rendered = json.dumps(rendered_json, indent=2, ensure_ascii=False) + "\n"
    changed = rendered != current
    backup = backup_config(path) if changed else None
    if changed:
        _atomic_write(path, rendered)
    mpath = manifest_path(home)
    payload = _read_manifest(mpath)
    installations = dict(payload.get("installations") or {})
    installations.pop(normalized, None)
    payload["installations"] = installations
    _write_json(mpath, payload)
    return InstallResult(normalized, path, backup, changed, mpath)


def rollback_config(config_path: Path, backup_path: Path) -> None:
    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError(str(backup_path))
    if backup_path.suffix != ".bak" or ".memory-mcp." not in backup_path.name:
        raise ValueError("backup path is not a Persistent Memory MCP backup")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, config_path)


def installation_manifest(home: Path | None = None) -> dict[str, Any]:
    return _read_manifest(manifest_path(home))
