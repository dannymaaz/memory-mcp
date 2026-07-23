"""Repository symbol indexing and compact impact analysis for Memory MCP."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .server_integration import _replace_registered_tool

SUPPORTED_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".toml", ".yaml", ".yml"}
DEFAULT_EXCLUDES = (
    ".git/*",
    ".venv/*",
    "venv/*",
    "node_modules/*",
    "dist/*",
    "build/*",
    "__pycache__/*",
)
MAX_FILES_DEFAULT = 2000
MAX_BYTES_DEFAULT = 2_000_000


@dataclass(frozen=True)
class Symbol:
    """A repository symbol with stable source coordinates."""

    id: str
    name: str
    kind: str
    file: str
    line: int
    end_line: int
    qualified_name: str
    purpose: str = ""
    last_verified_commit: str | None = None


@dataclass(frozen=True)
class Edge:
    """A typed relationship between repository entities."""

    source: str
    target: str
    relation: str
    confidence: float = 1.0


@dataclass
class RepositoryIndex:
    """Compact repository code-intelligence index."""

    root: str
    commit: str | None
    symbols: list[Symbol] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "commit": self.commit,
            "symbols": [asdict(item) for item in self.symbols],
            "edges": [asdict(item) for item in self.edges],
            "files_scanned": self.files_scanned,
            "files_skipped": self.files_skipped,
            "warnings": list(self.warnings),
        }


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _repository_root(path: str | os.PathLike[str]) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = _git(candidate, "rev-parse", "--show-toplevel")
    if root:
        return Path(root).resolve()
    if candidate.is_dir():
        return candidate
    raise ValueError(f"Repository path does not exist: {candidate}")


def _symbol_id(file: str, qualified_name: str, kind: str) -> str:
    value = f"{file}:{qualified_name}:{kind}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:20]


def _purpose(node: ast.AST) -> str:
    value = ast.get_docstring(node, clean=True) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else None
    if not value:
        return ""
    return value.splitlines()[0][:240]


def _python_symbols(path: Path, relative: str, commit: str | None) -> tuple[list[Symbol], list[Edge]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text, filename=relative)
    symbols: list[Symbol] = []
    edges: list[Edge] = []
    stack: list[str] = []
    symbol_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def _add(self, node: ast.AST, name: str, kind: str) -> str:
            qualified = ".".join([*stack, name])
            symbol_id = _symbol_id(relative, qualified, kind)
            symbols.append(
                Symbol(
                    id=symbol_id,
                    name=name,
                    kind=kind,
                    file=relative,
                    line=int(getattr(node, "lineno", 1)),
                    end_line=int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                    qualified_name=qualified,
                    purpose=_purpose(node),
                    last_verified_commit=commit,
                )
            )
            if symbol_stack:
                edges.append(Edge(symbol_stack[-1], symbol_id, "contains"))
            return symbol_id

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            symbol_id = self._add(node, node.name, "class")
            for base in node.bases:
                base_name = ast.unparse(base) if hasattr(ast, "unparse") else ""
                if base_name:
                    edges.append(Edge(symbol_id, f"external:{base_name}", "inherits", 0.8))
            stack.append(node.name)
            symbol_stack.append(symbol_id)
            self.generic_visit(node)
            symbol_stack.pop()
            stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            kind = "method" if stack else "function"
            symbol_id = self._add(node, node.name, kind)
            stack.append(node.name)
            symbol_stack.append(symbol_id)
            self.generic_visit(node)
            symbol_stack.pop()
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            if symbol_stack:
                target = ""
                if isinstance(node.func, ast.Name):
                    target = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    target = node.func.attr
                if target:
                    edges.append(Edge(symbol_stack[-1], f"name:{target}", "calls", 0.65))
            self.generic_visit(node)

    Visitor().visit(tree)
    return symbols, edges


_JS_SYMBOL = re.compile(
    r"^(?:export\s+)?(?:async\s+)?(?:(class)\s+([A-Za-z_$][\w$]*)|"
    r"(?:function)\s+([A-Za-z_$][\w$]*)|"
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
    re.MULTILINE,
)
_SQL_SYMBOL = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|VIEW|FUNCTION|TRIGGER|INDEX)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?([A-Za-z_][\w.]*)",
    re.IGNORECASE,
)


def _regex_symbols(path: Path, relative: str, commit: str | None) -> tuple[list[Symbol], list[Edge]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    symbols: list[Symbol] = []
    matcher = _SQL_SYMBOL if path.suffix.lower() == ".sql" else _JS_SYMBOL
    for match in matcher.finditer(text):
        if matcher is _SQL_SYMBOL:
            kind, name = match.group(1).lower(), match.group(2)
        else:
            class_marker, class_name, function_name, variable_name = match.groups()
            name = class_name or function_name or variable_name
            kind = "class" if class_marker else "function"
        line = text.count("\n", 0, match.start()) + 1
        symbols.append(
            Symbol(
                id=_symbol_id(relative, name, kind),
                name=name,
                kind=kind,
                file=relative,
                line=line,
                end_line=line,
                qualified_name=name,
                last_verified_commit=commit,
            )
        )
    return symbols, []


def _iter_files(root: Path, excludes: Iterable[str], max_files: int) -> Iterable[Path]:
    yielded = 0
    patterns = tuple(excludes)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(relative, pattern) for pattern in patterns):
            continue
        yield path
        yielded += 1
        if yielded >= max_files:
            return


def build_repository_index(
    repository_path: str,
    *,
    excludes: Iterable[str] = DEFAULT_EXCLUDES,
    max_files: int = MAX_FILES_DEFAULT,
    max_file_bytes: int = MAX_BYTES_DEFAULT,
) -> RepositoryIndex:
    """Index supported symbols and relationships without external parsers."""
    root = _repository_root(repository_path)
    commit = _git(root, "rev-parse", "HEAD")
    index = RepositoryIndex(root=str(root), commit=commit)
    by_name: dict[str, list[str]] = {}

    for path in _iter_files(root, excludes, max_files):
        relative = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > max_file_bytes:
                index.files_skipped += 1
                index.warnings.append(f"Skipped oversized file: {relative}")
                continue
            if path.suffix.lower() == ".py":
                symbols, edges = _python_symbols(path, relative, commit)
            else:
                symbols, edges = _regex_symbols(path, relative, commit)
        except (OSError, SyntaxError, UnicodeError) as exc:
            index.files_skipped += 1
            index.warnings.append(f"Could not index {relative}: {exc}")
            continue
        index.files_scanned += 1
        index.symbols.extend(symbols)
        index.edges.extend(edges)
        for symbol in symbols:
            by_name.setdefault(symbol.name, []).append(symbol.id)
            index.edges.append(Edge(f"file:{relative}", symbol.id, "defines"))

    resolved_edges: list[Edge] = []
    for edge in index.edges:
        if edge.target.startswith("name:"):
            name = edge.target.split(":", 1)[1]
            targets = by_name.get(name, [])
            if len(targets) == 1:
                resolved_edges.append(Edge(edge.source, targets[0], edge.relation, edge.confidence))
            else:
                resolved_edges.append(edge)
        else:
            resolved_edges.append(edge)
    index.edges = resolved_edges
    return index


def analyze_impact(index: RepositoryIndex, query: str, depth: int = 2, limit: int = 50) -> dict[str, Any]:
    """Return a bounded dependency subgraph around matching symbols or files."""
    normalized = query.casefold()
    seeds = {
        symbol.id
        for symbol in index.symbols
        if normalized in symbol.name.casefold()
        or normalized in symbol.qualified_name.casefold()
        or normalized in symbol.file.casefold()
    }
    if not seeds:
        return {"query": query, "matches": [], "nodes": [], "edges": [], "warnings": ["No matching symbol or file"]}

    selected = set(seeds)
    frontier = set(seeds)
    for _ in range(max(0, min(depth, 5))):
        next_frontier: set[str] = set()
        for edge in index.edges:
            if edge.source in frontier:
                next_frontier.add(edge.target)
            if edge.target in frontier:
                next_frontier.add(edge.source)
        next_frontier -= selected
        selected.update(next_frontier)
        frontier = next_frontier
        if not frontier or len(selected) >= limit:
            break
    selected = set(list(selected)[:limit])
    symbol_map = {symbol.id: symbol for symbol in index.symbols}
    nodes = [asdict(symbol_map[node]) for node in selected if node in symbol_map]
    edges = [asdict(edge) for edge in index.edges if edge.source in selected and edge.target in selected]
    duplicate_names = sorted(
        name for name in {item["name"] for item in nodes} if sum(node["name"] == name for node in nodes) > 1
    )
    return {
        "query": query,
        "matches": sorted(seeds),
        "nodes": nodes,
        "edges": edges,
        "duplicate_symbol_names": duplicate_names,
        "files": sorted({item["file"] for item in nodes}),
        "commit": index.commit,
    }


def find_existing_symbols(index: RepositoryIndex, requested_name: str) -> list[dict[str, Any]]:
    """Warn when a requested responsibility may already exist."""
    needle = requested_name.casefold().replace("_", " ")
    matches = []
    for symbol in index.symbols:
        haystack = f"{symbol.name} {symbol.qualified_name} {symbol.purpose}".casefold().replace("_", " ")
        if needle in haystack or haystack in needle:
            matches.append(asdict(symbol))
    return matches[:20]


def build_code_intelligence_tools(server_module: Any) -> tuple[Callable[..., dict[str, Any]], Callable[..., dict[str, Any]]]:
    """Build MCP-compatible repository indexing and impact tools."""
    cache: dict[str, RepositoryIndex] = {}

    def index_repository_symbols(repository_path: str, refresh: bool = False, max_files: int = MAX_FILES_DEFAULT) -> dict[str, Any]:
        root = str(_repository_root(repository_path))
        if refresh or root not in cache:
            cache[root] = build_repository_index(root, max_files=max_files)
        index = cache[root]
        return {"status": "ok", **index.as_dict(), "symbol_count": len(index.symbols), "edge_count": len(index.edges)}

    def analyze_symbol_impact(repository_path: str, query: str, depth: int = 2, refresh: bool = False) -> dict[str, Any]:
        root = str(_repository_root(repository_path))
        if refresh or root not in cache:
            cache[root] = build_repository_index(root)
        result = analyze_impact(cache[root], query, depth=depth)
        result["status"] = "ok"
        result["existing_symbols"] = find_existing_symbols(cache[root], query)
        return result

    return index_repository_symbols, analyze_symbol_impact


def install_code_intelligence(server_module: Any) -> tuple[Callable[..., dict[str, Any]], Callable[..., dict[str, Any]]]:
    """Install code-intelligence tools without rewriting the legacy server."""
    index_tool, impact_tool = build_code_intelligence_tools(server_module)
    tools = (
        ("index_repository_symbols", index_tool, "Indexa símbolos y relaciones de un repositorio."),
        ("analyze_symbol_impact", impact_tool, "Analiza impacto y dependencias de símbolos o archivos."),
    )
    for name, function, description in tools:
        function.__name__ = name
        setattr(server_module, name, function)
        if not _replace_registered_tool(server_module.server, name, function):
            try:
                server_module.server.tool(name=name, description=description)(function)
            except Exception:
                pass
    return index_tool, impact_tool
