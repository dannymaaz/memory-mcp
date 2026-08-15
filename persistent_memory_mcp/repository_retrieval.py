"""Progressive repository retrieval with bounded, provenance-aware fragments."""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .code_intelligence import (
    DEFAULT_EXCLUDES,
    SUPPORTED_SUFFIXES,
    Edge,
    RepositoryIndex,
    Symbol,
    _python_symbols,
    _regex_symbols,
)
from .context_packet import MIN_CONTEXT_PACKET_BUDGET
from .git_verification import GitSnapshot, file_sha256, repository_snapshot
from .security import redact_sensitive_value
from .server_integration import _replace_registered_tool
from .settings import RuntimeSettings
from .tokenization import TokenCounter, measure_tokens, resolve_token_counter

_WORD_RE = re.compile(r"[A-Za-z0-9_./-]+")
_CURSOR_VERSION = 1
_MAX_LIMIT = 10_000


@dataclass(frozen=True)
class RetrievalLimits:
    """Hard limits for one progressive repository retrieval request."""

    max_depth: int = 4
    max_index_files: int = 2000
    max_files: int = 12
    max_symbols: int = 80
    max_neighbors: int = 24
    max_fragments: int = 8
    max_file_bytes: int = 512_000
    max_total_bytes: int = 64_000
    max_fragment_lines: int = 80
    page_size: int = 12
    token_budget: int = 1600

    def __post_init__(self) -> None:
        bounded = {
            "max_depth": (self.max_depth, 1, 12),
            "max_index_files": (self.max_index_files, 1, 5000),
            "max_files": (self.max_files, 1, 100),
            "max_symbols": (self.max_symbols, 1, 500),
            "max_neighbors": (self.max_neighbors, 0, 200),
            "max_fragments": (self.max_fragments, 1, 50),
            "max_file_bytes": (self.max_file_bytes, 1, 2_000_000),
            "max_total_bytes": (self.max_total_bytes, 1, 1_000_000),
            "max_fragment_lines": (self.max_fragment_lines, 1, 300),
            "page_size": (self.page_size, 1, 50),
            "token_budget": (self.token_budget, MIN_CONTEXT_PACKET_BUDGET, 100_000),
        }
        for name, (value, minimum, maximum) in bounded.items():
            if not minimum <= int(value) <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")


@dataclass(frozen=True)
class RankedFile:
    path: str
    score: float
    reasons: tuple[str, ...]
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "score": round(self.score, 4),
            "reasons": list(self.reasons),
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class RankedSymbol:
    symbol: Symbol
    score: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self.symbol)
        payload["score"] = round(self.score, 4)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass
class ProgressiveRepositoryRetriever:
    """Retrieve repository evidence in bounded map → file → symbol → fragment stages."""

    ignore_patterns: tuple[str, ...] = ()
    _index_cache: dict[tuple[str, str, tuple[str, ...]], RepositoryIndex] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def _patterns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*DEFAULT_EXCLUDES, *self.ignore_patterns)))

    def _ignored(self, relative: str) -> bool:
        normalized = relative.replace("\\", "/").lstrip("./")
        name = Path(normalized).name
        for pattern in self._patterns():
            candidate = pattern.replace("\\", "/").lstrip("./")
            if fnmatch.fnmatch(normalized, candidate) or fnmatch.fnmatch(name, candidate):
                return True
            prefix = candidate.removesuffix("/**").removesuffix("/*")
            if prefix and normalized.startswith(prefix.rstrip("/") + "/"):
                return True
        return False

    def _tracked_files(self, snapshot: GitSnapshot, limits: RetrievalLimits) -> list[str]:
        completed = subprocess.run(
            [
                "git",
                "-C",
                snapshot.repository,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        raw = completed.stdout.decode("utf-8", errors="replace")
        files: list[str] = []
        root = Path(snapshot.repository).resolve()
        for value in raw.split("\0"):
            if not value:
                continue
            relative = value.replace("\\", "/")
            if self._ignored(relative) or Path(relative).suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            try:
                self._safe_file(root, relative)
            except ValueError:
                continue
            files.append(relative)
            if len(files) >= limits.max_index_files:
                break
        return sorted(set(files))

    def _safe_file(self, root: Path, relative: str) -> Path:
        candidate_text = str(relative).replace("\\", "/")
        if not candidate_text or Path(candidate_text).is_absolute():
            raise ValueError("repository file path must be relative")
        if any(part in {"", ".", ".."} for part in Path(candidate_text).parts):
            raise ValueError(f"unsafe repository path: {relative!r}")
        candidate = (root / candidate_text).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"repository path escapes root: {relative!r}") from exc
        if not candidate.is_file():
            raise ValueError(f"repository file does not exist: {relative!r}")
        return candidate

    @staticmethod
    def _terms(value: str) -> tuple[str, ...]:
        return tuple(sorted({item.casefold() for item in _WORD_RE.findall(value) if len(item) > 1}))

    def _grep_hits(
        self,
        snapshot: GitSnapshot,
        files: Iterable[str],
        query: str,
    ) -> set[str]:
        """Use Git's local search to identify candidate files without loading them into Python."""
        terms = [term for term in self._terms(query) if len(term) >= 3][:8]
        if not terms:
            return set()
        command = ["git", "-C", snapshot.repository, "grep", "-I", "-l", "-F"]
        for term in terms:
            command.extend(["-e", term])
        command.append("--")
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode not in {0, 1}:
            return set()
        allowed = set(files)
        hits = {
            line.strip().replace("\\", "/")
            for line in completed.stdout.splitlines()
            if line.strip()
        }
        return {item for item in hits if item in allowed and not self._ignored(item)}

    def _repository_map(
        self,
        files: Iterable[str],
        *,
        limits: RetrievalLimits,
    ) -> list[dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {
            ".": {"path": ".", "files": 0, "extensions": set()}
        }
        for relative in files:
            path = Path(relative)
            suffix = path.suffix.lower() or "[none]"
            nodes["."]["files"] += 1
            nodes["."]["extensions"].add(suffix)
            parents = list(path.parents)[:-1]
            for parent in parents:
                if str(parent) == ".":
                    continue
                depth = len(parent.parts)
                if depth > limits.max_depth:
                    continue
                key = parent.as_posix()
                node = nodes.setdefault(
                    key,
                    {"path": key, "files": 0, "extensions": set()},
                )
                node["files"] += 1
                node["extensions"].add(suffix)
        result = []
        for key in sorted(nodes, key=lambda value: (value != ".", value.count("/"), value)):
            node = nodes[key]
            result.append(
                {
                    "path": node["path"],
                    "files": int(node["files"]),
                    "extensions": sorted(node["extensions"]),
                }
            )
        return result[: min(200, limits.max_index_files)]

    def _rank_files(
        self,
        root: Path,
        files: Iterable[str],
        query: str,
        grep_hits: set[str],
        *,
        limits: RetrievalLimits,
    ) -> list[RankedFile]:
        terms = self._terms(query)
        normalized_query = " ".join(terms)
        ranked: list[RankedFile] = []
        for relative in files:
            path = self._safe_file(root, relative)
            rendered = relative.casefold()
            stem = path.stem.casefold()
            reasons: list[str] = []
            score = 0.0
            if relative in grep_hits:
                score += 7.0
                reasons.append("git-grep-content-match")
            if normalized_query and normalized_query in rendered:
                score += 8.0
                reasons.append("query-in-path")
            matched_terms = [term for term in terms if term in rendered]
            if matched_terms:
                score += 5.0 * (len(matched_terms) / max(1, len(terms)))
                reasons.append("path-term-overlap")
            if stem in terms or any(stem in term for term in terms if len(stem) >= 3):
                score += 4.0
                reasons.append("basename-match")
            extension_term = path.suffix.lower().lstrip(".")
            if extension_term and extension_term in terms:
                score += 1.5
                reasons.append("language-match")
            depth = len(Path(relative).parts)
            score += max(0.0, 1.0 - (depth - 1) * 0.1)
            ranked.append(
                RankedFile(
                    path=relative,
                    score=score,
                    reasons=tuple(reasons or ("stable-path-fallback",)),
                    size_bytes=path.stat().st_size,
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.path))
        return ranked[: limits.max_files]

    def _selected_index(
        self,
        snapshot: GitSnapshot,
        ranked_files: Iterable[RankedFile],
        *,
        limits: RetrievalLimits,
    ) -> RepositoryIndex:
        selected = tuple(item.path for item in ranked_files)
        cache_key = (snapshot.repository, snapshot.commit_sha, selected)
        if not snapshot.dirty and cache_key in self._index_cache:
            return self._index_cache[cache_key]

        root = Path(snapshot.repository).resolve()
        index = RepositoryIndex(root=snapshot.repository, commit=snapshot.commit_sha)
        by_name: dict[str, list[str]] = {}
        for relative in selected:
            path = self._safe_file(root, relative)
            if self._ignored(relative):
                continue
            try:
                if path.stat().st_size > limits.max_file_bytes:
                    index.files_skipped += 1
                    index.warnings.append(f"Skipped oversized file: {relative}")
                    continue
                if path.suffix.lower() == ".py":
                    symbols, edges = _python_symbols(path, relative, snapshot.commit_sha)
                else:
                    symbols, edges = _regex_symbols(path, relative, snapshot.commit_sha)
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

        resolved: list[Edge] = []
        for edge in index.edges:
            if edge.target.startswith("name:"):
                name = edge.target.split(":", 1)[1]
                targets = sorted(by_name.get(name, []))
                if len(targets) == 1:
                    resolved.append(Edge(edge.source, targets[0], edge.relation, edge.confidence))
                    continue
            resolved.append(edge)
        index.edges = resolved
        if not snapshot.dirty:
            self._index_cache[cache_key] = index
        return index

    def _rank_symbols(
        self,
        index: RepositoryIndex,
        query: str,
        *,
        limits: RetrievalLimits,
    ) -> list[RankedSymbol]:
        terms = self._terms(query)
        normalized_query = query.strip().casefold()
        scores: dict[str, tuple[float, list[str]]] = {}
        symbol_map = {symbol.id: symbol for symbol in index.symbols}

        for symbol in index.symbols:
            name = symbol.name.casefold()
            qualified = symbol.qualified_name.casefold()
            path = symbol.file.casefold()
            purpose = symbol.purpose.casefold()
            reasons: list[str] = []
            score = 0.0
            if normalized_query and normalized_query in {name, qualified}:
                score += 12.0
                reasons.append("exact-symbol-match")
            elif normalized_query and normalized_query in qualified:
                score += 8.0
                reasons.append("query-in-symbol")
            matched = [term for term in terms if term in name or term in qualified]
            if matched:
                score += 7.0 * (len(matched) / max(1, len(terms)))
                reasons.append("symbol-term-overlap")
            path_matched = [term for term in terms if term in path]
            if path_matched:
                score += 3.0 * (len(path_matched) / max(1, len(terms)))
                reasons.append("path-term-overlap")
            purpose_matched = [term for term in terms if term in purpose]
            if purpose_matched:
                score += 2.0 * (len(purpose_matched) / max(1, len(terms)))
                reasons.append("purpose-term-overlap")
            scores[symbol.id] = (score, reasons or ["stable-symbol-fallback"])

        direct = sorted(
            scores,
            key=lambda symbol_id: (
                -scores[symbol_id][0],
                symbol_map[symbol_id].file,
                symbol_map[symbol_id].line,
                symbol_map[symbol_id].qualified_name,
            ),
        )[: limits.max_symbols]
        seeds = [symbol_id for symbol_id in direct if scores[symbol_id][0] > 0][:8]
        neighbor_ids: set[str] = set()
        frontier = set(seeds)
        for _ in range(max(0, limits.max_depth - 1)):
            if not frontier or len(neighbor_ids) >= limits.max_neighbors:
                break
            next_frontier: set[str] = set()
            for edge in sorted(
                index.edges,
                key=lambda item: (item.source, item.target, item.relation),
            ):
                if edge.source in frontier and edge.target in symbol_map:
                    next_frontier.add(edge.target)
                if edge.target in frontier and edge.source in symbol_map:
                    next_frontier.add(edge.source)
            next_frontier -= set(seeds)
            next_frontier -= neighbor_ids
            for symbol_id in sorted(next_frontier):
                if len(neighbor_ids) >= limits.max_neighbors:
                    break
                neighbor_ids.add(symbol_id)
                score, reasons = scores[symbol_id]
                scores[symbol_id] = (score + 1.5, [*reasons, "graph-neighbor"])
            frontier = next_frontier

        pool = set(direct) | neighbor_ids
        ranked = [
            RankedSymbol(symbol_map[symbol_id], scores[symbol_id][0], tuple(scores[symbol_id][1]))
            for symbol_id in pool
            if symbol_id in symbol_map
        ]
        ranked.sort(
            key=lambda item: (
                -item.score,
                item.symbol.file,
                item.symbol.line,
                item.symbol.qualified_name,
            )
        )
        return ranked[: limits.max_symbols]

    def _state_fingerprint(
        self,
        root: Path,
        snapshot: GitSnapshot,
        query: str,
        ranked_files: Iterable[RankedFile],
    ) -> str:
        digest = hashlib.sha256()
        digest.update(snapshot.commit_sha.encode("utf-8"))
        digest.update(b"\0")
        digest.update(query.strip().casefold().encode("utf-8"))
        for ranked in ranked_files:
            digest.update(b"\0")
            digest.update(ranked.path.encode("utf-8"))
            digest.update(b":")
            digest.update((file_sha256(root, ranked.path) or "missing").encode("ascii"))
        return digest.hexdigest()[:24]

    def _decode_cursor(self, cursor: str | None, fingerprint: str) -> int:
        if not cursor:
            return 0
        try:
            padding = "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid repository retrieval cursor") from exc
        if payload.get("v") != _CURSOR_VERSION:
            raise ValueError("unsupported repository retrieval cursor version")
        if payload.get("fingerprint") != fingerprint:
            raise ValueError("repository retrieval cursor is stale or belongs to another query")
        offset = int(payload.get("offset", -1))
        if offset < 0 or offset > _MAX_LIMIT:
            raise ValueError("invalid repository retrieval cursor offset")
        return offset

    def _encode_cursor(self, offset: int, fingerprint: str) -> str:
        payload = {"v": _CURSOR_VERSION, "offset": offset, "fingerprint": fingerprint}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _fragment(
        self,
        root: Path,
        snapshot: GitSnapshot,
        ranked: RankedSymbol,
        *,
        limits: RetrievalLimits,
        remaining_bytes: int,
    ) -> dict[str, Any] | None:
        symbol = ranked.symbol
        if self._ignored(symbol.file):
            return None
        path = self._safe_file(root, symbol.file)
        size = path.stat().st_size
        if size > limits.max_file_bytes:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if not lines:
            return None
        start = max(1, int(symbol.line) - 2)
        declared_end = max(int(symbol.end_line), int(symbol.line))
        if declared_end == int(symbol.line):
            declared_end += min(20, limits.max_fragment_lines - 1)
        end = min(len(lines), declared_end + 2, start + limits.max_fragment_lines - 1)
        content = "\n".join(lines[start - 1 : end])
        redacted = redact_sensitive_value(content)
        safe_content = str(redacted.value)
        encoded = safe_content.encode("utf-8")
        if len(encoded) > remaining_bytes:
            if remaining_bytes < 64:
                return None
            safe_content = encoded[:remaining_bytes].decode("utf-8", errors="ignore")
            encoded = safe_content.encode("utf-8")
        fragment_sha = hashlib.sha256(encoded).hexdigest()
        return {
            "symbol_id": symbol.id,
            "symbol": symbol.qualified_name,
            "kind": symbol.kind,
            "path": symbol.file,
            "start_line": start,
            "end_line": end,
            "content": safe_content,
            "content_sha256": fragment_sha,
            "file_sha256": file_sha256(root, symbol.file),
            "bytes": len(encoded),
            "redactions": sorted(set(redacted.redactions)),
            "provenance": {
                "repository": snapshot.repository,
                "commit": snapshot.commit_sha,
                "ref": snapshot.branch or "HEAD",
                "working_tree_dirty": snapshot.dirty,
                "path": symbol.file,
                "start_line": start,
                "end_line": end,
            },
        }

    @staticmethod
    def _apply_token_measurement(payload: dict[str, Any], counter: TokenCounter) -> int:
        usage = payload["token_usage"]
        previous: tuple[int, int] | None = None
        for _ in range(8):
            measurement = measure_tokens(payload, counter)
            signature = (measurement.count, measurement.estimated_count)
            usage.update(
                {
                    "count": measurement.count,
                    "tokenizer": measurement.tokenizer,
                    "model": measurement.model,
                    "mode": "exact" if measurement.exact else "estimated",
                    "fallback": measurement.fallback,
                }
            )
            if signature == previous:
                break
            previous = signature
        final = measure_tokens(payload, counter)
        usage.update(
            {
                "count": final.count,
                "tokenizer": final.tokenizer,
                "model": final.model,
                "mode": "exact" if final.exact else "estimated",
                "fallback": final.fallback,
            }
        )
        return final.count

    def _fit_budget(self, payload: dict[str, Any], counter: TokenCounter, budget: int) -> None:
        usage = payload["token_usage"]
        while True:
            count = self._apply_token_measurement(payload, counter)
            if count <= budget:
                return
            trimmed = False
            for key in ("fragments", "symbol_candidates", "file_candidates", "repository_map"):
                value = payload.get(key)
                if isinstance(value, list) and value:
                    value.pop()
                    trimmed = True
                    usage["truncated_for_budget"] = True
                    break
            if not trimmed:
                raise ValueError(
                    f"repository retrieval control metadata exceeds token budget: {count} > {budget}"
                )

    def retrieve(
        self,
        repository_path: str,
        query: str,
        *,
        cursor: str | None = None,
        limits: RetrievalLimits | None = None,
        model: str | None = None,
        tokenizer: str | TokenCounter | None = "auto",
    ) -> dict[str, Any]:
        """Retrieve bounded repository evidence without reading every file's content."""
        active_limits = limits or RetrievalLimits()
        snapshot = repository_snapshot(repository_path)
        root = Path(snapshot.repository).resolve()
        files = self._tracked_files(snapshot, active_limits)
        repository_map = self._repository_map(files, limits=active_limits)
        grep_hits = self._grep_hits(snapshot, files, query)
        ranked_files = self._rank_files(
            root,
            files,
            query,
            grep_hits,
            limits=active_limits,
        )
        index = self._selected_index(snapshot, ranked_files, limits=active_limits)
        ranked_symbols = self._rank_symbols(index, query, limits=active_limits)
        fingerprint = self._state_fingerprint(root, snapshot, query, ranked_files)

        offset = self._decode_cursor(cursor, fingerprint)
        page_end = min(len(ranked_symbols), offset + active_limits.page_size)
        page = ranked_symbols[offset:page_end]
        next_cursor = (
            self._encode_cursor(page_end, fingerprint)
            if page_end < len(ranked_symbols)
            else None
        )

        fragments: list[dict[str, Any]] = []
        emitted_bytes = 0
        for ranked in page[: active_limits.max_fragments]:
            fragment = self._fragment(
                root,
                snapshot,
                ranked,
                limits=active_limits,
                remaining_bytes=active_limits.max_total_bytes - emitted_bytes,
            )
            if fragment is None:
                continue
            fragments.append(fragment)
            emitted_bytes += int(fragment["bytes"])
            if emitted_bytes >= active_limits.max_total_bytes:
                break

        counter = resolve_token_counter(model=model, tokenizer=tokenizer)
        payload: dict[str, Any] = {
            "status": "ok",
            "query": query,
            "repository": {
                "root": snapshot.repository,
                "branch": snapshot.branch,
                "commit": snapshot.commit_sha,
                "dirty": snapshot.dirty,
            },
            "stages": ["map", "files", "symbols", "fragments"],
            "repository_map": repository_map,
            "file_candidates": [item.as_dict() for item in ranked_files],
            "symbol_candidates": [item.as_dict() for item in page],
            "fragments": fragments,
            "pagination": {
                "offset": offset,
                "page_size": active_limits.page_size,
                "returned": len(page),
                "total_ranked_symbols": len(ranked_symbols),
                "next_cursor": next_cursor,
            },
            "limits": asdict(active_limits),
            "index": {
                "files_scanned": index.files_scanned,
                "files_skipped": index.files_skipped,
                "symbols": len(index.symbols),
                "warnings": list(index.warnings)[:20],
                "grep_candidates": len(grep_hits),
            },
            "token_usage": {
                "budget": active_limits.token_budget,
                "count": 0,
                "tokenizer": counter.name,
                "model": counter.model,
                "mode": "exact" if counter.exact else "estimated",
                "fallback": not counter.exact,
                "truncated_for_budget": False,
            },
        }
        self._fit_budget(payload, counter, active_limits.token_budget)
        return payload


def build_progressive_retrieval_tool(settings: RuntimeSettings) -> Any:
    """Build the MCP-compatible retrieval tool using validated runtime ignore policy."""
    retriever = ProgressiveRepositoryRetriever(ignore_patterns=settings.ignore_patterns)

    def retrieve_repository_context(
        repository_path: str,
        query: str,
        cursor: str | None = None,
        token_budget: int = 1600,
        max_files: int = 12,
        max_symbols: int = 80,
        max_fragments: int = 8,
        page_size: int = 12,
        max_depth: int = 4,
        model: str | None = None,
        tokenizer: str = "auto",
    ) -> dict[str, Any]:
        limits = RetrievalLimits(
            token_budget=token_budget,
            max_files=max_files,
            max_symbols=max_symbols,
            max_fragments=max_fragments,
            page_size=page_size,
            max_depth=max_depth,
        )
        return retriever.retrieve(
            repository_path,
            query,
            cursor=cursor,
            limits=limits,
            model=model,
            tokenizer=tokenizer,
        )

    retrieve_repository_context.__name__ = "retrieve_repository_context"
    retrieve_repository_context.__doc__ = (
        "Recupera contexto de repositorio por mapa, archivos, símbolos y fragmentos acotados."
    )
    return retrieve_repository_context


def install_progressive_retrieval(server_module: Any, settings: RuntimeSettings) -> Any:
    """Install progressive repository retrieval after Git/code intelligence."""
    tool = build_progressive_retrieval_tool(settings)
    setattr(server_module, tool.__name__, tool)
    if not _replace_registered_tool(server_module.server, tool.__name__, tool):
        try:
            server_module.server.tool(
                name=tool.__name__,
                description=(
                    "Recupera evidencia de repositorio progresivamente sin cargar archivos completos."
                ),
            )(tool)
        except Exception:
            pass
    return tool
