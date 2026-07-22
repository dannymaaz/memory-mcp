"""Storage adapters for local and remote Persistent Memory MCP backends."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, runtime_checkable

JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]


@runtime_checkable
class StorageAdapter(Protocol):
    """Minimal backend contract used by the MCP service layer."""

    backend_name: str

    def initialize(self) -> None: ...

    def select(self, table: str, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def insert(self, table: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...

    def upsert(
        self,
        table: str,
        payload: Mapping[str, Any],
        conflict_columns: Iterable[str] | None = None,
    ) -> dict[str, Any]: ...

    def delete(self, table: str, filters: Mapping[str, Any]) -> int: ...

    def healthcheck(self) -> tuple[bool, str]: ...


_CONFLICT_COLUMNS: dict[str, tuple[str, ...]] = {
    "workspaces": ("owner_id", "slug"),
    "projects": ("owner_id", "slug"),
    "preferences": ("project_id", "preference_key"),
    "session_state": ("session_id",),
    "file_memory": ("project_id", "file_path"),
    "file_relations": ("project_id", "source_file", "target_file", "relation_type"),
    "prompt_patterns": ("project_id", "title"),
    "retention_policies": ("project_id",),
    "memory_documents": ("project_id", "source_type", "source_id"),
}


class SQLiteStorage:
    """Local-first SQLite implementation with explicit table allow-listing."""

    backend_name = "sqlite"
    allowed_tables = frozenset(
        {
            "workspaces",
            "projects",
            "architecture",
            "decisions",
            "tasks",
            "preferences",
            "warnings",
            "sessions",
            "session_state",
            "interface_logs",
            "checkpoints",
            "file_memory",
            "file_relations",
            "prompt_patterns",
            "memory_documents",
            "timeline_events",
            "retention_policies",
        }
    )

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        connection.execute("pragma journal_mode = wal")
        return connection

    def initialize(self) -> None:
        schema_path = Path(__file__).with_name("sqlite_schema.sql")
        with self.connect() as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))

    def _validate_table(self, table: str) -> str:
        if table not in self.allowed_tables:
            raise ValueError(f"Unsupported storage table: {table}")
        return table

    @staticmethod
    def _encode(value: Any) -> Any:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, bool):
            return int(value)
        return value

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in (
            "metadata",
            "payload",
            "keywords",
            "repo_status",
            "state",
            "blockers",
            "next_steps",
            "symbols",
            "preference_value",
        ):
            value = result.get(key)
            if isinstance(value, str) and value and value[:1] in "[{":
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
        for key, value in tuple(result.items()):
            if key.startswith("is_") or key in {"summarize_archived"}:
                if isinstance(value, int):
                    result[key] = bool(value)
        return result

    @staticmethod
    def _where(filters: Mapping[str, Any] | None) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        clauses = [f'"{key}" = ?' for key in filters]
        return " where " + " and ".join(clauses), [SQLiteStorage._encode(value) for value in filters.values()]

    def select(self, table: str, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        table = self._validate_table(table)
        where_sql, params = self._where(filters)
        with self.connect() as connection:
            rows = connection.execute(f'select * from "{table}"{where_sql}', params).fetchall()
        return [self._decode_row(row) for row in rows]

    def insert(self, table: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        table = self._validate_table(table)
        if not payload:
            raise ValueError("payload cannot be empty")
        columns = list(payload)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(f'"{column}"' for column in columns)
        values = [self._encode(payload[column]) for column in columns]
        with self.connect() as connection:
            cursor = connection.execute(
                f'insert into "{table}" ({column_sql}) values ({placeholders})', values
            )
            connection.commit()
            row = connection.execute(
                f'select * from "{table}" where rowid = ?', (cursor.lastrowid,)
            ).fetchone()
        return self._decode_row(row) if row is not None else dict(payload)

    def upsert(
        self,
        table: str,
        payload: Mapping[str, Any],
        conflict_columns: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        table = self._validate_table(table)
        columns = list(payload)
        conflicts = list(
            conflict_columns
            or (["id"] if payload.get("id") else _CONFLICT_COLUMNS.get(table, ()))
        )
        if not conflicts:
            return self.insert(table, payload)
        if any(column not in columns for column in conflicts):
            return self.insert(table, payload)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(f'"{column}"' for column in columns)
        conflict_sql = ", ".join(f'"{column}"' for column in conflicts)
        update_columns = [column for column in columns if column not in conflicts]
        if update_columns:
            update_sql = ", ".join(f'"{column}" = excluded."{column}"' for column in update_columns)
            action = f"do update set {update_sql}"
        else:
            action = "do nothing"
        values = [self._encode(payload[column]) for column in columns]
        with self.connect() as connection:
            connection.execute(
                f'insert into "{table}" ({column_sql}) values ({placeholders}) '
                f'on conflict ({conflict_sql}) {action}',
                values,
            )
            connection.commit()
        filters = {column: payload[column] for column in conflicts}
        rows = self.select(table, filters)
        return rows[0] if rows else dict(payload)

    def delete(self, table: str, filters: Mapping[str, Any]) -> int:
        table = self._validate_table(table)
        if not filters:
            raise ValueError("destructive operations require filters")
        if table != "workspaces" and ("owner_id" not in filters or "project_id" not in filters):
            raise ValueError("delete requires owner_id and project_id scope")
        where_sql, params = self._where(filters)
        with self.connect() as connection:
            cursor = connection.execute(f'delete from "{table}"{where_sql}', params)
            connection.commit()
            return int(cursor.rowcount)

    def healthcheck(self) -> tuple[bool, str]:
        try:
            with self.connect() as connection:
                version = connection.execute("select sqlite_version()").fetchone()[0]
            return True, f"SQLite {version} at {self.path}"
        except sqlite3.Error as exc:
            return False, str(exc)


class SQLiteQuery:
    """Small PostgREST-like query facade used by the existing MCP server."""

    def __init__(self, storage: SQLiteStorage, table: str) -> None:
        self.storage = storage
        self.table_name = table
        self.operation = "select"
        self.payload: Mapping[str, Any] | None = None
        self.filters: dict[str, Any] = {}

    def select(self, _columns: str = "*") -> "SQLiteQuery":
        self.operation = "select"
        return self

    def insert(self, payload: Mapping[str, Any]) -> "SQLiteQuery":
        self.operation = "insert"
        self.payload = payload
        return self

    def upsert(self, payload: Mapping[str, Any]) -> "SQLiteQuery":
        self.operation = "upsert"
        self.payload = payload
        return self

    def delete(self) -> "SQLiteQuery":
        self.operation = "delete"
        return self

    def eq(self, key: str, value: Any) -> "SQLiteQuery":
        self.filters[key] = value
        return self

    def execute(self) -> SimpleNamespace:
        if self.operation == "select":
            data: Any = self.storage.select(self.table_name, self.filters)
        elif self.operation == "insert":
            if self.payload is None:
                raise ValueError("insert payload is required")
            data = [self.storage.insert(self.table_name, self.payload)]
        elif self.operation == "upsert":
            if self.payload is None:
                raise ValueError("upsert payload is required")
            data = [self.storage.upsert(self.table_name, self.payload)]
        elif self.operation == "delete":
            data = {"count": self.storage.delete(self.table_name, self.filters)}
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported SQLite operation: {self.operation}")
        return SimpleNamespace(data=data)


class SQLiteClient:
    """Supabase-client-compatible facade for the existing service layer."""

    backend_name = "sqlite"

    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage
        self.options = SimpleNamespace(headers={})
        self.postgrest = SimpleNamespace(headers={})
        self.owner_id = ""

    def table(self, name: str) -> SQLiteQuery:
        return SQLiteQuery(self.storage, name)

    def rpc(self, _function_name: str, _params: Mapping[str, Any]) -> SQLiteQuery:
        raise NotImplementedError("SQLite semantic RPC is not available; lexical fallback is used")


def normalize_backend(value: str | None) -> str:
    """Normalize supported backend aliases."""

    normalized = (value or "supabase").strip().lower()
    aliases = {"postgres": "postgresql", "local": "sqlite"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"sqlite", "supabase", "postgresql"}:
        raise ValueError("MEMORY_BACKEND must be sqlite, supabase, or postgresql")
    return normalized


def create_storage(backend: str, *, sqlite_path: str | Path | None = None) -> StorageAdapter:
    """Create a configured storage adapter without importing remote dependencies."""

    normalized = normalize_backend(backend)
    if normalized == "sqlite":
        storage = SQLiteStorage(sqlite_path or Path.home() / ".memory-mcp" / "memory.db")
        storage.initialize()
        return storage
    raise ValueError(f"Backend {normalized} uses the existing remote client, not a local adapter")


def create_sqlite_client(path: str | Path | None = None) -> SQLiteClient:
    """Create and initialize the SQLite facade used by the MCP server."""

    resolved = path or os.getenv("SQLITE_PATH") or Path.home() / ".memory-mcp" / "memory.db"
    storage = SQLiteStorage(resolved)
    storage.initialize()
    return SQLiteClient(storage)
