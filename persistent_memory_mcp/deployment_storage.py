"""Storage parity hooks for deployment history."""

from __future__ import annotations

from typing import Any

_DEPLOYMENT_SQL = """
create table if not exists deployment_records (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  service text not null,
  environment text not null,
  host text not null,
  directory text not null,
  restart_command text not null,
  commit_sha text not null,
  result text not null,
  operator text,
  tests text not null default '[]',
  rollback_target text,
  rollback_plan text not null default '{}',
  risk_level text not null default 'low',
  risk_reasons text not null default '[]',
  confirmation_recorded integer not null default 0,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);
create index if not exists idx_deployment_scope
  on deployment_records(owner_id, project_id, service, environment, created_at desc);
"""


def install_deployment_storage() -> None:
    """Extend SQLite safely before the legacy server creates its storage client."""
    from .storage import SQLiteStorage

    if getattr(SQLiteStorage, "_deployment_storage_installed", False):
        return
    SQLiteStorage.allowed_tables = frozenset((*SQLiteStorage.allowed_tables, "deployment_records"))
    original_initialize = SQLiteStorage.initialize

    def initialize(self: Any) -> None:
        original_initialize(self)
        with self.connect() as connection:
            connection.executescript(_DEPLOYMENT_SQL)

    SQLiteStorage.initialize = initialize
    SQLiteStorage._deployment_storage_installed = True
