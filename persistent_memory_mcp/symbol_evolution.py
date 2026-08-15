"""Persistent Git-grounded symbol snapshots, evolution and typed evidence links."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .code_intelligence import DEFAULT_EXCLUDES, RepositoryIndex, Symbol, build_repository_index
from .git_verification import GitSnapshot, file_sha256, repository_snapshot
from .security import redact_sensitive_value
from .server_integration import _replace_registered_tool
from .settings import RuntimeSettings
from .tokenization import TokenCounter, measure_tokens, resolve_token_counter

_SCHEMA_VERSION = 2
_MAX_SIGNATURE_CHARS = 512
_MAX_HISTORY_LIMIT = 100
_MAX_SOURCE_FILE_BYTES = 1_000_000
_VERIFICATION_STATES = frozenset(
    {"verified", "stale", "contradicted", "missing_source", "unverified"}
)
_MANUAL_TARGET_TABLES = {"decision": "decisions", "task": "tasks"}


class SymbolEvolutionError(RuntimeError):
    """Base error for persistent code-evolution operations."""


class SymbolEvolutionSchemaError(SymbolEvolutionError):
    """Raised when the local database has not applied the symbol-evolution migration."""


class SymbolEvolutionScopeError(SymbolEvolutionError):
    """Raised when owner/project scope cannot be verified."""


@dataclass(frozen=True)
class CapturedSymbol:
    """Bounded symbol metadata prepared for persistence without storing source bodies."""

    source_symbol_id: str
    name: str
    qualified_name: str
    kind: str
    path: str
    language: str
    line: int
    end_line: int
    signature: str
    signature_sha256: str
    body_sha256: str
    file_sha256: str


@dataclass(frozen=True)
class MatchedSymbol:
    """Current symbol associated with its stable logical identity and optional predecessor."""

    current: CapturedSymbol
    logical_id: str
    first_seen_commit: str
    old: Mapping[str, Any] | None
    confidence: float


def _digest(*parts: object, prefix: str = "") -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(str(part).encode("utf-8", errors="replace"))
        hasher.update(b"\0")
    value = hasher.hexdigest()
    return f"{prefix}{value}" if prefix else value


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if check and completed.returncode != 0:
        raise SymbolEvolutionError(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def _language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".sql": "sql",
    }.get(suffix, suffix.lstrip("."))


def _is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").casefold()
    name = Path(normalized).name
    return (
        normalized.startswith("tests/")
        or "/tests/" in normalized
        or normalized.startswith("test/")
        or "/test/" in normalized
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class SymbolEvolutionService:
    """Persist and query bounded symbol evolution inside the local SQLite database."""

    def __init__(
        self,
        database: str | Path,
        *,
        owner_id: str,
        ignore_patterns: Iterable[str] = (),
    ) -> None:
        self.database = Path(database).expanduser().resolve()
        self.owner_id = owner_id.strip()
        if not self.owner_id:
            raise SymbolEvolutionScopeError("OWNER_ID is required for persistent symbol evolution")
        self.ignore_patterns = tuple(dict.fromkeys((*DEFAULT_EXCLUDES, *tuple(ignore_patterns))))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        connection.execute("pragma journal_mode = wal")
        return connection

    def _assert_schema(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("pragma user_version").fetchone()[0])
        if version < _SCHEMA_VERSION:
            raise SymbolEvolutionSchemaError(
                "symbol evolution requires SQLite schema v2; run memory-mcp-migrate preview/apply first"
            )
        required = {
            "code_symbol_snapshot_runs",
            "code_symbol_snapshots",
            "code_symbol_changes",
            "code_symbol_links",
        }
        found = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table' and name in (?,?,?,?)",
                tuple(sorted(required)),
            ).fetchall()
        }
        if found != required:
            missing = ", ".join(sorted(required - found))
            raise SymbolEvolutionSchemaError(f"symbol evolution schema is incomplete: {missing}")

    def _assert_project(self, connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
        row = connection.execute(
            "select id, owner_id, repo_path from projects where id = ? and owner_id = ?",
            (project_id, self.owner_id),
        ).fetchone()
        if row is None:
            raise SymbolEvolutionScopeError("project does not exist inside the active owner scope")
        return dict(row)

    @staticmethod
    def _commit_metadata(root: Path) -> tuple[str, str | None]:
        raw = _git(root, "show", "-s", "--format=%an%x00%aI", "HEAD")
        author, _, commit_time = raw.partition("\0")
        return author[:200], commit_time or None

    def _existing_run(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        repository: str,
        commit_sha: str,
    ) -> dict[str, Any] | None:
        return _row_dict(
            connection.execute(
                "select * from code_symbol_snapshot_runs "
                "where owner_id=? and project_id=? and repository=? and commit_sha=?",
                (self.owner_id, project_id, repository, commit_sha),
            ).fetchone()
        )

    def _nearest_ancestor_run(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        root: Path,
        current_commit: str,
    ) -> dict[str, Any] | None:
        rows = connection.execute(
            "select * from code_symbol_snapshot_runs "
            "where owner_id=? and project_id=? and repository=? and commit_sha<>? "
            "order by captured_at desc limit 100",
            (self.owner_id, project_id, str(root), current_commit),
        ).fetchall()
        best: tuple[int, dict[str, Any]] | None = None
        for row in rows:
            candidate = dict(row)
            completed = subprocess.run(
                ["git", "-C", str(root), "merge-base", "--is-ancestor", candidate["commit_sha"], current_commit],
                check=False,
                capture_output=True,
                timeout=10,
            )
            if completed.returncode != 0:
                continue
            try:
                distance = int(_git(root, "rev-list", "--count", f"{candidate['commit_sha']}..{current_commit}"))
            except (ValueError, SymbolEvolutionError):
                continue
            if distance <= 0:
                continue
            if best is None or distance < best[0]:
                best = (distance, candidate)
        return best[1] if best else None

    @staticmethod
    def _source_span(
        symbols: list[Symbol],
        index: int,
        lines: list[str],
    ) -> tuple[int, int]:
        symbol = symbols[index]
        start = max(1, int(symbol.line))
        declared_end = max(start, int(symbol.end_line))
        if declared_end > start:
            end = min(len(lines), declared_end)
        elif index + 1 < len(symbols):
            end = max(start, min(len(lines), int(symbols[index + 1].line) - 1))
        else:
            end = len(lines)
        return start, max(start, end)

    def _capture_symbols(self, root: Path, index: RepositoryIndex) -> list[CapturedSymbol]:
        grouped: dict[str, list[Symbol]] = defaultdict(list)
        for symbol in index.symbols:
            grouped[symbol.file].append(symbol)

        captured: list[CapturedSymbol] = []
        for relative, symbols in sorted(grouped.items()):
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise SymbolEvolutionError(f"indexed symbol escaped repository root: {relative}") from exc
            if not path.is_file() or path.stat().st_size > _MAX_SOURCE_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            file_hash = file_sha256(root, relative)
            if not file_hash:
                continue
            ordered = sorted(symbols, key=lambda item: (item.line, item.end_line, item.qualified_name))
            for position, symbol in enumerate(ordered):
                start, end = self._source_span(ordered, position, lines)
                body = "\n".join(lines[start - 1 : end])
                signature_raw = " ".join(lines[start - 1 : min(end, start + 7)]).strip()
                redacted = redact_sensitive_value(signature_raw)
                signature = " ".join(str(redacted.value).split())[:_MAX_SIGNATURE_CHARS]
                captured.append(
                    CapturedSymbol(
                        source_symbol_id=symbol.id,
                        name=symbol.name,
                        qualified_name=symbol.qualified_name,
                        kind=symbol.kind,
                        path=relative,
                        language=_language(relative),
                        line=start,
                        end_line=end,
                        signature=signature,
                        signature_sha256=_digest(signature_raw),
                        body_sha256=_digest(body),
                        file_sha256=file_hash,
                    )
                )
        captured.sort(key=lambda item: (item.path, item.line, item.kind, item.qualified_name))
        return captured

    @staticmethod
    def _unique_map(items: Iterable[Any], key: Any) -> dict[Any, Any]:
        buckets: dict[Any, list[Any]] = defaultdict(list)
        for item in items:
            buckets[key(item)].append(item)
        return {bucket_key: values[0] for bucket_key, values in buckets.items() if len(values) == 1}

    def _match_symbols(
        self,
        current: list[CapturedSymbol],
        previous: list[dict[str, Any]],
        repository: str,
        commit_sha: str,
    ) -> tuple[list[MatchedSymbol], list[dict[str, Any]]]:
        unmatched_current = set(range(len(current)))
        unmatched_previous = set(range(len(previous)))
        matches: dict[int, tuple[int, float]] = {}

        strategies = (
            (
                lambda value: (value.kind, value.qualified_name),
                lambda value: (value["kind"], value["qualified_name"]),
                1.0,
            ),
            (
                lambda value: (value.kind, value.body_sha256),
                lambda value: (value["kind"], value["body_sha256"]),
                0.98,
            ),
            (
                lambda value: (value.kind, value.name, value.signature_sha256),
                lambda value: (value["kind"], value["name"], value["signature_sha256"]),
                0.85,
            ),
        )
        for current_key, previous_key, confidence in strategies:
            current_map = self._unique_map(
                (current[index] for index in unmatched_current), current_key
            )
            previous_map = self._unique_map(
                (previous[index] for index in unmatched_previous), previous_key
            )
            previous_positions = {
                previous_key(previous[index]): index for index in unmatched_previous
            }
            current_positions = {current_key(current[index]): index for index in unmatched_current}
            for key_value in sorted(set(current_map) & set(previous_map), key=str):
                current_index = current_positions[key_value]
                previous_index = previous_positions[key_value]
                matches[current_index] = (previous_index, confidence)
                unmatched_current.discard(current_index)
                unmatched_previous.discard(previous_index)

        matched: list[MatchedSymbol] = []
        for index, symbol in enumerate(current):
            match = matches.get(index)
            if match is None:
                logical_id = _digest(
                    self.owner_id,
                    repository,
                    commit_sha,
                    symbol.source_symbol_id,
                    prefix="sym_",
                )[:68]
                matched.append(
                    MatchedSymbol(symbol, logical_id, commit_sha, None, 1.0)
                )
                continue
            previous_index, confidence = match
            old = previous[previous_index]
            matched.append(
                MatchedSymbol(
                    symbol,
                    str(old["logical_id"]),
                    str(old["first_seen_commit"]),
                    old,
                    confidence,
                )
            )
        deleted = [previous[index] for index in sorted(unmatched_previous)]
        return matched, deleted

    @staticmethod
    def _change_type(match: MatchedSymbol) -> tuple[str, dict[str, bool]]:
        old = match.old
        if old is None:
            return "added", {
                "path_changed": False,
                "name_changed": False,
                "signature_changed": False,
                "body_changed": False,
            }
        current = match.current
        path_changed = str(old["path"]) != current.path
        name_changed = (
            str(old["name"]) != current.name
            or str(old["qualified_name"]) != current.qualified_name
        )
        signature_changed = str(old["signature_sha256"]) != current.signature_sha256
        body_changed = str(old["body_sha256"]) != current.body_sha256
        if str(old["name"]) != current.name:
            change_type = "renamed"
        elif path_changed or str(old["qualified_name"]) != current.qualified_name:
            change_type = "moved"
        elif signature_changed or body_changed:
            change_type = "modified"
        else:
            change_type = "unchanged"
        return change_type, {
            "path_changed": path_changed,
            "name_changed": name_changed,
            "signature_changed": signature_changed,
            "body_changed": body_changed,
        }

    @staticmethod
    def _snapshot_id(run_id: str, source_symbol_id: str) -> str:
        return _digest(run_id, source_symbol_id, prefix="snap_")[:69]

    @staticmethod
    def _test_links(index: RepositoryIndex, logical_by_source: Mapping[str, tuple[str, str]]) -> list[tuple[str, str, str, str]]:
        symbol_by_id = {symbol.id: symbol for symbol in index.symbols}
        links: set[tuple[str, str, str, str]] = set()
        for edge in index.edges:
            if edge.relation != "calls" or edge.target not in logical_by_source:
                continue
            source = symbol_by_id.get(edge.source)
            if source is None or not _is_test_path(source.file):
                continue
            logical_id, snapshot_id = logical_by_source[edge.target]
            evidence_hash = _digest(source.id, edge.target, edge.relation)
            links.add((logical_id, snapshot_id, source.file, evidence_hash))
        return sorted(links)

    def capture(
        self,
        project_id: str,
        repository_path: str,
        *,
        max_files: int = 2000,
        max_file_bytes: int = 512_000,
    ) -> dict[str, Any]:
        """Capture the current clean HEAD idempotently and persist its evolution from the nearest ancestor run."""
        snapshot = repository_snapshot(repository_path)
        if snapshot.dirty:
            raise SymbolEvolutionError(
                "persistent symbol snapshots require a clean Git working tree"
            )
        if not snapshot.commit_sha:
            raise SymbolEvolutionError("repository has no HEAD commit to snapshot")
        root = Path(snapshot.repository).resolve()

        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            existing = self._existing_run(
                connection, project_id, str(root), snapshot.commit_sha
            )
            if existing is not None:
                return {
                    "status": "current",
                    "run": existing,
                    "idempotent": True,
                }
            parent_run = self._nearest_ancestor_run(
                connection, project_id, root, snapshot.commit_sha
            )
            previous: list[dict[str, Any]] = []
            if parent_run is not None:
                previous = [
                    dict(row)
                    for row in connection.execute(
                        "select * from code_symbol_snapshots where run_id=? "
                        "order by path, line, qualified_name",
                        (parent_run["id"],),
                    ).fetchall()
                ]
        finally:
            connection.close()

        index = build_repository_index(
            str(root),
            excludes=self.ignore_patterns,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )
        captured = self._capture_symbols(root, index)
        matched, deleted = self._match_symbols(
            captured, previous, str(root), snapshot.commit_sha
        )
        revalidated = repository_snapshot(str(root))
        if revalidated.commit_sha != snapshot.commit_sha or revalidated.dirty:
            raise SymbolEvolutionError(
                "repository changed while the symbol snapshot was being prepared"
            )

        run_id = _digest(
            self.owner_id,
            project_id,
            str(root),
            snapshot.commit_sha,
            prefix="run_",
        )[:68]
        commit_author, commit_time = self._commit_metadata(root)
        ref = snapshot.branch or "HEAD"
        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            connection.execute("begin immediate")
            existing = self._existing_run(
                connection, project_id, str(root), snapshot.commit_sha
            )
            if existing is not None:
                connection.rollback()
                return {"status": "current", "run": existing, "idempotent": True}

            connection.execute(
                "insert into code_symbol_snapshot_runs(" 
                "id,project_id,owner_id,repository,commit_sha,ref,commit_author,commit_time," 
                "symbol_count,files_scanned,files_skipped,metadata) "
                "values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    project_id,
                    self.owner_id,
                    str(root),
                    snapshot.commit_sha,
                    ref,
                    commit_author,
                    commit_time,
                    len(matched),
                    index.files_scanned,
                    index.files_skipped,
                    json.dumps(
                        {"warnings": index.warnings[:20]},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
            )

            logical_by_source: dict[str, tuple[str, str]] = {}
            changes: dict[str, int] = defaultdict(int)
            for match in matched:
                symbol = match.current
                snapshot_id = self._snapshot_id(run_id, symbol.source_symbol_id)
                logical_by_source[symbol.source_symbol_id] = (match.logical_id, snapshot_id)
                connection.execute(
                    "insert into code_symbol_snapshots(" 
                    "id,run_id,project_id,owner_id,repository,commit_sha,ref,logical_id," 
                    "source_symbol_id,path,name,qualified_name,kind,language,line,end_line,signature," 
                    "signature_sha256,body_sha256,file_sha256,first_seen_commit,verification_state) "
                    "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        snapshot_id,
                        run_id,
                        project_id,
                        self.owner_id,
                        str(root),
                        snapshot.commit_sha,
                        ref,
                        match.logical_id,
                        symbol.source_symbol_id,
                        symbol.path,
                        symbol.name,
                        symbol.qualified_name,
                        symbol.kind,
                        symbol.language,
                        symbol.line,
                        symbol.end_line,
                        symbol.signature,
                        symbol.signature_sha256,
                        symbol.body_sha256,
                        symbol.file_sha256,
                        match.first_seen_commit,
                        "verified",
                    ),
                )
                change_type, flags = self._change_type(match)
                changes[change_type] += 1
                old_snapshot_id = match.old.get("id") if match.old else None
                connection.execute(
                    "insert into code_symbol_changes(" 
                    "project_id,owner_id,repository,from_run_id,to_run_id,from_commit,to_commit," 
                    "logical_id,old_snapshot_id,new_snapshot_id,change_type,path_changed,name_changed," 
                    "signature_changed,body_changed,confidence) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        self.owner_id,
                        str(root),
                        parent_run.get("id") if parent_run else None,
                        run_id,
                        parent_run.get("commit_sha") if parent_run else None,
                        snapshot.commit_sha,
                        match.logical_id,
                        old_snapshot_id,
                        snapshot_id,
                        change_type,
                        int(flags["path_changed"]),
                        int(flags["name_changed"]),
                        int(flags["signature_changed"]),
                        int(flags["body_changed"]),
                        match.confidence,
                    ),
                )
                automatic_links = (
                    ("defined_in", "file", symbol.path, symbol.path, symbol.file_sha256),
                    ("observed_at", "commit", snapshot.commit_sha, ref, _digest(snapshot.commit_sha)),
                )
                for relation, target_type, target_id, target_ref, evidence_hash in automatic_links:
                    connection.execute(
                        "insert or ignore into code_symbol_links(" 
                        "project_id,owner_id,repository,logical_id,snapshot_id,relation_type,target_type," 
                        "target_id,target_ref,verification_state,evidence_sha256) values(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            project_id,
                            self.owner_id,
                            str(root),
                            match.logical_id,
                            snapshot_id,
                            relation,
                            target_type,
                            target_id,
                            target_ref,
                            "verified",
                            evidence_hash,
                        ),
                    )

            for old in deleted:
                changes["deleted"] += 1
                connection.execute(
                    "insert into code_symbol_changes(" 
                    "project_id,owner_id,repository,from_run_id,to_run_id,from_commit,to_commit," 
                    "logical_id,old_snapshot_id,new_snapshot_id,change_type,path_changed,name_changed," 
                    "signature_changed,body_changed,confidence) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        self.owner_id,
                        str(root),
                        parent_run.get("id") if parent_run else None,
                        run_id,
                        parent_run.get("commit_sha") if parent_run else None,
                        snapshot.commit_sha,
                        old["logical_id"],
                        old["id"],
                        None,
                        "deleted",
                        0,
                        0,
                        0,
                        0,
                        1.0,
                    ),
                )

            for logical_id, snapshot_id, test_path, evidence_hash in self._test_links(
                index, logical_by_source
            ):
                connection.execute(
                    "insert or ignore into code_symbol_links(" 
                    "project_id,owner_id,repository,logical_id,snapshot_id,relation_type,target_type," 
                    "target_id,target_ref,verification_state,evidence_sha256) values(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        self.owner_id,
                        str(root),
                        logical_id,
                        snapshot_id,
                        "tested_by",
                        "test",
                        test_path,
                        test_path,
                        "verified",
                        evidence_hash,
                    ),
                )

            connection.commit()
            run = self._existing_run(connection, project_id, str(root), snapshot.commit_sha)
            return {
                "status": "ok",
                "run": run,
                "idempotent": False,
                "parent_commit": parent_run.get("commit_sha") if parent_run else None,
                "changes": dict(sorted(changes.items())),
                "symbol_count": len(matched),
                "deleted_count": len(deleted),
                "test_links": len(self._test_links(index, logical_by_source)),
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _resolve_logical_id(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        repository: str,
        symbol: str,
    ) -> str:
        needle = symbol.strip()
        if not needle:
            raise ValueError("symbol is required")
        direct = connection.execute(
            "select logical_id from code_symbol_snapshots where owner_id=? and project_id=? "
            "and repository=? and logical_id=? limit 1",
            (self.owner_id, project_id, repository, needle),
        ).fetchone()
        if direct is not None:
            return str(direct[0])
        rows = connection.execute(
            "select logical_id,name,qualified_name,created_at from code_symbol_snapshots "
            "where owner_id=? and project_id=? and repository=? and (name=? or qualified_name=?) "
            "order by created_at desc limit 20",
            (self.owner_id, project_id, repository, needle, needle),
        ).fetchall()
        logical_ids = list(dict.fromkeys(str(row["logical_id"]) for row in rows))
        if not logical_ids:
            raise SymbolEvolutionError(f"no persisted symbol matches {symbol!r}")
        if len(logical_ids) > 1:
            raise SymbolEvolutionError(
                f"symbol name is ambiguous; use a qualified name or logical_id: {symbol!r}"
            )
        return logical_ids[0]

    def _effective_state(
        self,
        repository: str,
        latest: Mapping[str, Any] | None,
        latest_change: Mapping[str, Any] | None,
    ) -> str:
        if latest_change and latest_change.get("change_type") == "deleted" and not latest_change.get("new_snapshot_id"):
            return "missing_source"
        if latest is None:
            return "missing_source"
        try:
            current = repository_snapshot(repository)
        except Exception:
            return "missing_source"
        if current.commit_sha != latest.get("commit_sha") or current.dirty:
            return "stale"
        path = Path(current.repository) / str(latest.get("path") or "")
        if not path.is_file():
            return "missing_source"
        current_hash = file_sha256(Path(current.repository), str(latest["path"]))
        if current_hash != latest.get("file_sha256"):
            return "stale"
        return str(latest.get("verification_state") or "unverified")

    def history(
        self,
        project_id: str,
        repository_path: str,
        symbol: str,
        *,
        limit: int = 20,
        token_budget: int = 1800,
        tokenizer: str | TokenCounter | None = "auto",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Return bounded snapshots, changes and typed evidence with explicit current/stale state."""
        if not 1 <= limit <= _MAX_HISTORY_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_HISTORY_LIMIT}")
        if token_budget < 256:
            raise ValueError("token_budget must be at least 256")
        root = str(Path(repository_path).expanduser().resolve())
        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            logical_id = self._resolve_logical_id(connection, project_id, root, symbol)
            snapshots = [
                dict(row)
                for row in connection.execute(
                    "select id,run_id,commit_sha,ref,logical_id,path,name,qualified_name,kind,language," 
                    "line,end_line,signature,signature_sha256,body_sha256,file_sha256,first_seen_commit," 
                    "verification_state,created_at from code_symbol_snapshots "
                    "where owner_id=? and project_id=? and repository=? and logical_id=? "
                    "order by created_at desc limit ?",
                    (self.owner_id, project_id, root, logical_id, limit),
                ).fetchall()
            ]
            changes = [
                dict(row)
                for row in connection.execute(
                    "select from_commit,to_commit,change_type,path_changed,name_changed,signature_changed," 
                    "body_changed,confidence,created_at from code_symbol_changes "
                    "where owner_id=? and project_id=? and repository=? and logical_id=? "
                    "order by created_at desc limit ?",
                    (self.owner_id, project_id, root, logical_id, limit),
                ).fetchall()
            ]
            links = [
                dict(row)
                for row in connection.execute(
                    "select id,relation_type,target_type,target_id,target_ref,verification_state," 
                    "evidence_sha256,metadata,created_at,updated_at from code_symbol_links "
                    "where owner_id=? and project_id=? and repository=? and logical_id=? "
                    "order by target_type,relation_type,target_id limit ?",
                    (self.owner_id, project_id, root, logical_id, min(limit * 4, 100)),
                ).fetchall()
            ]
        finally:
            connection.close()
        latest = snapshots[0] if snapshots else None
        latest_change = changes[0] if changes else None
        state = self._effective_state(root, latest, latest_change)
        payload: dict[str, Any] = {
            "status": "ok",
            "logical_id": logical_id,
            "current_state": state,
            "latest": latest,
            "snapshots": snapshots,
            "changes": changes,
            "links": links,
            "token_usage": {
                "budget": token_budget,
                "count": 0,
                "tokenizer": "",
                "model": model,
                "truncated": False,
            },
        }
        counter = resolve_token_counter(model=model, tokenizer=tokenizer)
        self._fit_budget(payload, counter, token_budget)
        return payload

    @staticmethod
    def _fit_budget(payload: dict[str, Any], counter: TokenCounter, budget: int) -> None:
        usage = payload["token_usage"]
        while True:
            measurement = measure_tokens(payload, counter)
            usage.update(
                {
                    "count": measurement.count,
                    "tokenizer": measurement.tokenizer,
                    "model": measurement.model,
                    "mode": "exact" if measurement.exact else "estimated",
                    "fallback": measurement.fallback,
                }
            )
            if measurement.count <= budget:
                return
            removed = False
            for key in ("snapshots", "changes", "links"):
                values = payload.get(key)
                if isinstance(values, list) and len(values) > 1:
                    values.pop()
                    usage["truncated"] = True
                    removed = True
                    break
            if not removed:
                raise ValueError(
                    f"symbol evolution control metadata exceeds token budget: {measurement.count} > {budget}"
                )

    def compare_commits(
        self,
        project_id: str,
        repository_path: str,
        from_commit: str,
        to_commit: str,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return the persisted classified diff for an exact captured commit pair."""
        if not 1 <= limit <= _MAX_HISTORY_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_HISTORY_LIMIT}")
        root = str(Path(repository_path).expanduser().resolve())
        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            rows = [
                dict(row)
                for row in connection.execute(
                    "select logical_id,old_snapshot_id,new_snapshot_id,change_type,path_changed," 
                    "name_changed,signature_changed,body_changed,confidence,created_at "
                    "from code_symbol_changes where owner_id=? and project_id=? and repository=? "
                    "and from_commit=? and to_commit=? order by change_type,logical_id limit ?",
                    (self.owner_id, project_id, root, from_commit, to_commit, limit),
                ).fetchall()
            ]
        finally:
            connection.close()
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            counts[str(row["change_type"])] += 1
        return {
            "status": "ok",
            "from_commit": from_commit,
            "to_commit": to_commit,
            "changes": rows,
            "counts": dict(sorted(counts.items())),
        }

    def link_memory(
        self,
        project_id: str,
        repository_path: str,
        symbol: str,
        *,
        target_type: str,
        target_id: str,
        relation_type: str = "related_to",
    ) -> dict[str, Any]:
        """Create a typed verified decision/task link only after validating project scope."""
        normalized_type = target_type.strip().lower()
        table = _MANUAL_TARGET_TABLES.get(normalized_type)
        if table is None:
            raise ValueError("manual target_type must be decision or task")
        root = str(Path(repository_path).expanduser().resolve())
        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            logical_id = self._resolve_logical_id(connection, project_id, root, symbol)
            target = connection.execute(
                f"select id from {table} where id=? and owner_id=? and project_id=?",
                (target_id, self.owner_id, project_id),
            ).fetchone()
            if target is None:
                raise SymbolEvolutionScopeError(
                    f"{normalized_type} target does not exist inside active owner/project scope"
                )
            latest = connection.execute(
                "select id from code_symbol_snapshots where owner_id=? and project_id=? and repository=? "
                "and logical_id=? order by created_at desc limit 1",
                (self.owner_id, project_id, root, logical_id),
            ).fetchone()
            evidence_hash = _digest(logical_id, normalized_type, target_id, relation_type)
            connection.execute(
                "insert into code_symbol_links(project_id,owner_id,repository,logical_id,snapshot_id," 
                "relation_type,target_type,target_id,target_ref,verification_state,evidence_sha256) "
                "values(?,?,?,?,?,?,?,?,?,?,?) "
                "on conflict(owner_id,project_id,repository,logical_id,relation_type,target_type,target_id) "
                "do update set snapshot_id=excluded.snapshot_id,verification_state='verified'," 
                "evidence_sha256=excluded.evidence_sha256,updated_at=datetime('now')",
                (
                    project_id,
                    self.owner_id,
                    root,
                    logical_id,
                    latest["id"] if latest else None,
                    relation_type[:80],
                    normalized_type,
                    target_id,
                    target_id,
                    "verified",
                    evidence_hash,
                ),
            )
            connection.commit()
            row = connection.execute(
                "select * from code_symbol_links where owner_id=? and project_id=? and repository=? "
                "and logical_id=? and relation_type=? and target_type=? and target_id=?",
                (
                    self.owner_id,
                    project_id,
                    root,
                    logical_id,
                    relation_type[:80],
                    normalized_type,
                    target_id,
                ),
            ).fetchone()
            return {"status": "ok", "link": dict(row) if row else None}
        finally:
            connection.close()

    def invalidate_link(
        self,
        project_id: str,
        link_id: str,
        *,
        state: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Explicitly invalidate evidence without deleting its history."""
        normalized_state = state.strip().lower()
        if normalized_state not in _VERIFICATION_STATES - {"verified"}:
            raise ValueError(
                "invalidation state must be stale, contradicted, missing_source, or unverified"
            )
        redacted = redact_sensitive_value(reason)
        metadata = json.dumps(
            {"reason": " ".join(str(redacted.value).split())[:300]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        connection = self._connect()
        try:
            self._assert_schema(connection)
            self._assert_project(connection, project_id)
            cursor = connection.execute(
                "update code_symbol_links set verification_state=?,metadata=?,updated_at=datetime('now') "
                "where id=? and owner_id=? and project_id=?",
                (normalized_state, metadata, link_id, self.owner_id, project_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise SymbolEvolutionScopeError("evidence link was not found in active scope")
            connection.commit()
            row = connection.execute(
                "select * from code_symbol_links where id=? and owner_id=? and project_id=?",
                (link_id, self.owner_id, project_id),
            ).fetchone()
            return {"status": "ok", "link": dict(row) if row else None}
        finally:
            connection.close()


def build_symbol_evolution_tools(settings: RuntimeSettings) -> tuple[Any, ...]:
    """Build local SQLite symbol-evolution MCP tools from validated runtime settings."""
    if settings.backend != "sqlite":
        return ()
    if not settings.owner_id:
        return ()
    service = SymbolEvolutionService(
        settings.sqlite_path,
        owner_id=settings.owner_id,
        ignore_patterns=settings.ignore_patterns,
    )

    def capture_symbol_snapshot(
        project_id: str,
        repository_path: str,
        max_files: int = 2000,
        max_file_bytes: int = 512000,
    ) -> dict[str, Any]:
        return service.capture(
            project_id,
            repository_path,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )

    def get_symbol_history(
        project_id: str,
        repository_path: str,
        symbol: str,
        limit: int = 20,
        token_budget: int = 1800,
        model: str | None = None,
        tokenizer: str = "auto",
    ) -> dict[str, Any]:
        return service.history(
            project_id,
            repository_path,
            symbol,
            limit=limit,
            token_budget=token_budget,
            model=model,
            tokenizer=tokenizer,
        )

    def compare_symbol_commits(
        project_id: str,
        repository_path: str,
        from_commit: str,
        to_commit: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        return service.compare_commits(
            project_id,
            repository_path,
            from_commit,
            to_commit,
            limit=limit,
        )

    def link_symbol_memory(
        project_id: str,
        repository_path: str,
        symbol: str,
        target_type: str,
        target_id: str,
        relation_type: str = "related_to",
    ) -> dict[str, Any]:
        return service.link_memory(
            project_id,
            repository_path,
            symbol,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
        )

    def invalidate_symbol_evidence(
        project_id: str,
        link_id: str,
        state: str,
        reason: str = "",
    ) -> dict[str, Any]:
        return service.invalidate_link(project_id, link_id, state=state, reason=reason)

    tools = (
        capture_symbol_snapshot,
        get_symbol_history,
        compare_symbol_commits,
        link_symbol_memory,
        invalidate_symbol_evidence,
    )
    for tool in tools:
        tool.__name__ = tool.__name__
    return tools


def install_symbol_evolution(server_module: Any, settings: RuntimeSettings) -> tuple[Any, ...]:
    """Install persistent symbol-evolution tools for the SQLite local-first runtime."""
    descriptions = {
        "capture_symbol_snapshot": "Captura símbolos del HEAD limpio y persiste evolución por commit.",
        "get_symbol_history": "Consulta historia, cambios y evidencia tipada de un símbolo persistido.",
        "compare_symbol_commits": "Compara cambios de símbolos entre dos snapshots persistidos.",
        "link_symbol_memory": "Enlaza un símbolo con una decisión o tarea validada del mismo proyecto.",
        "invalidate_symbol_evidence": "Invalida evidencia de símbolo explícitamente sin borrar historial.",
    }
    tools = build_symbol_evolution_tools(settings)
    for tool in tools:
        name = tool.__name__
        setattr(server_module, name, tool)
        if not _replace_registered_tool(server_module.server, name, tool):
            try:
                server_module.server.tool(name=name, description=descriptions[name])(tool)
            except Exception:
                pass
    return tools
