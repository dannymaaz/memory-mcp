from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from persistent_memory_mcp.code_intelligence import (
    analyze_impact,
    build_code_intelligence_tools,
    build_repository_index,
    find_existing_symbols,
    install_code_intelligence,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.com")
    _git(root, "config", "user.name", "Tests")
    (root / "service.py").write_text(
        '"""Example service."""\n\n'
        "class Store:\n"
        '    """Persist values."""\n'
        "    def save(self, value):\n"
        "        return normalize(value)\n\n"
        "def normalize(value):\n"
        '    """Normalize a value."""\n'
        "    return str(value).strip()\n",
        encoding="utf-8",
    )
    (root / "consumer.py").write_text(
        "from service import Store\n\n"
        "def publish(value):\n"
        "    return Store().save(value)\n",
        encoding="utf-8",
    )
    (root / "schema.sql").write_text(
        "CREATE TABLE IF NOT EXISTS memories (id text primary key);\n",
        encoding="utf-8",
    )
    (root / "frontend.ts").write_text(
        "export function renderMemory() { return true; }\n"
        "export class MemoryCard {}\n",
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    return root


def test_build_repository_index_extracts_symbols_and_edges(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    index = build_repository_index(str(root))

    names = {symbol.name for symbol in index.symbols}
    kinds = {(symbol.name, symbol.kind) for symbol in index.symbols}

    assert {"Store", "save", "normalize", "publish", "memories", "renderMemory"} <= names
    assert ("Store", "class") in kinds
    assert ("save", "method") in kinds
    assert ("memories", "table") in kinds
    assert index.commit == _git(root, "rev-parse", "HEAD")
    assert all(symbol.last_verified_commit == index.commit for symbol in index.symbols)
    assert any(edge.relation == "defines" for edge in index.edges)
    assert any(edge.relation == "calls" for edge in index.edges)


def test_analyze_impact_returns_bounded_dependency_graph(tmp_path: Path) -> None:
    index = build_repository_index(str(_repository(tmp_path)))
    result = analyze_impact(index, "normalize", depth=2)

    assert result["matches"]
    assert any(node["name"] == "normalize" for node in result["nodes"])
    assert "service.py" in result["files"]
    assert result["commit"] == index.commit


def test_find_existing_symbols_warns_about_existing_responsibility(tmp_path: Path) -> None:
    index = build_repository_index(str(_repository(tmp_path)))

    matches = find_existing_symbols(index, "normalize")

    assert matches
    assert matches[0]["name"] == "normalize"


def test_index_limits_oversized_files(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "large.py").write_text("x = 1\n" * 100, encoding="utf-8")

    index = build_repository_index(str(root), max_file_bytes=10)

    assert index.files_skipped >= 1
    assert any("oversized" in warning for warning in index.warnings)


def test_tools_cache_index_and_support_refresh(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    index_tool, impact_tool = build_code_intelligence_tools(SimpleNamespace())

    first = index_tool(str(root))
    impact = impact_tool(str(root), "Store")
    refreshed = index_tool(str(root), refresh=True)

    assert first["status"] == "ok"
    assert first["symbol_count"] > 0
    assert impact["status"] == "ok"
    assert impact["existing_symbols"]
    assert refreshed["commit"] == first["commit"]


def test_install_registers_tools_on_fallback_server(tmp_path: Path) -> None:
    root = _repository(tmp_path)

    class FakeServer:
        def __init__(self) -> None:
            self._tools: dict[str, object] = {}

        def tool(self, name: str, description: str):
            del description

            def register(function):
                self._tools[name] = function
                return function

            return register

    module = SimpleNamespace(server=FakeServer())

    index_tool, impact_tool = install_code_intelligence(module)

    assert module.index_repository_symbols is index_tool
    assert module.analyze_symbol_impact is impact_tool
    assert set(module.server._tools) == {"index_repository_symbols", "analyze_symbol_impact"}
    assert index_tool(str(root))["status"] == "ok"
