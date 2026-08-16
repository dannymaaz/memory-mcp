"""Bounded read-only maintenance status for the localhost Dashboard."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .maintenance import HealthError, HealthService
from .security import redact_sensitive_value
from .storage import SQLiteStorage

_VERIFICATION_STATES = (
    "verified",
    "stale",
    "contradicted",
    "missing_source",
    "unverified",
)
_SENSITIVITY_TABLES = (
    "decisions",
    "tasks",
    "warnings",
    "file_memory",
    "prompt_patterns",
    "memory_documents",
)


class DashboardStatusError(ValueError):
    """Raised when a bounded maintenance status cannot be resolved safely."""


def _resolve_owner(storage: SQLiteStorage, configured_owner: str | None) -> str:
    owner = str(configured_owner or "").strip()
    if owner:
        return owner
    with storage.connect() as connection:
        rows = connection.execute(
            "select distinct owner_id from projects "
            "where owner_id is not null and trim(owner_id) != '' "
            "order by owner_id asc limit 2"
        ).fetchall()
    owners = [str(row[0]) for row in rows]
    if len(owners) == 1:
        return owners[0]
    if not owners:
        raise DashboardStatusError(
            "maintenance owner is not configured and no project owner can be inferred"
        )
    raise DashboardStatusError(
        "maintenance owner must be configured when multiple owners exist"
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "select 1 from sqlite_master where type='table' and name=?", (table,)
        ).fetchone()
        is not None
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'pragma table_info("{table}")').fetchall()
    }


class DashboardStatusService:
    """Compose existing maintenance/evidence signals into a compact Dashboard payload."""

    def __init__(
        self,
        storage: SQLiteStorage,
        *,
        owner_id: str | None = None,
        backup_directory: str | Path | None = None,
    ) -> None:
        self.storage = storage
        self.owner_id = _resolve_owner(storage, owner_id)
        self.backup_directory = (
            Path(backup_directory).expanduser().resolve()
            if backup_directory is not None
            else None
        )

    def read(self, *, project_id: str | None = None) -> dict[str, Any]:
        owner = self.owner_id
        project = str(project_id or "").strip() or None
        with self.storage.connect() as connection:
            if project:
                row = connection.execute(
                    "select id from projects where id=? and owner_id=?",
                    (project, owner),
                ).fetchone()
                if row is None:
                    raise DashboardStatusError(
                        "project does not exist inside the active owner scope"
                    )
            verification = self._verification_summary(connection, owner, project)
            sensitivity = self._sensitivity_summary(connection, owner, project)

        try:
            health = HealthService(
                self.storage.path,
                backup_directory=self.backup_directory,
            ).check(full_integrity=False)
        except HealthError as exc:
            raise DashboardStatusError(str(exc)) from exc

        health_dict = health.as_dict()
        payload = {
            "status": health.status,
            "owner_configured": True,
            "project_id": project,
            "health": {
                "status": health.status,
                "maintenance_ready": health.maintenance_ready,
                "schema_version": health.schema_version,
                "sqlite_version": health.sqlite_version,
                "journal_mode": health.journal_mode,
                "quick_check": list(health.quick_check),
                "missing_indexes": list(health.missing_indexes),
                "foreign_key_violations": len(health.foreign_key_violations),
            },
            "storage": {
                "database_size_bytes": health.database_size_bytes,
                "wal_size_bytes": health.wal_size_bytes,
                "shm_size_bytes": health.shm_size_bytes,
                "disk_free_bytes": health.disk_free_bytes,
            },
            "backup": {
                "configured": self.backup_directory is not None,
                "latest_verified": health.latest_verified_backup,
                "invalid_manifests": health.invalid_backup_manifests,
            },
            "verification": verification,
            "sensitivity": sensitivity,
            "read_only": True,
        }
        # Do not leak any accidental path-like fields added by future HealthResult changes.
        del health_dict
        return redact_sensitive_value(payload).value

    @staticmethod
    def _verification_summary(
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "snapshot_states": {state: 0 for state in _VERIFICATION_STATES},
            "evidence_states": {state: 0 for state in _VERIFICATION_STATES},
        }
        for table, target in (
            ("code_symbol_snapshots", "snapshot_states"),
            ("code_symbol_links", "evidence_states"),
        ):
            if not _table_exists(connection, table):
                continue
            clauses = ["owner_id=?"]
            params: list[Any] = [owner_id]
            if project_id:
                clauses.append("project_id=?")
                params.append(project_id)
            rows = connection.execute(
                f'select verification_state, count(*) from "{table}" '
                f"where {' and '.join(clauses)} group by verification_state",
                params,
            ).fetchall()
            for state, count in rows:
                key = str(state)
                if key in result[target]:
                    result[target][key] = int(count)
        risk_total = sum(
            int(count)
            for state, count in result["evidence_states"].items()
            if state != "verified"
        )
        result["evidence_risk_count"] = risk_total
        return result

    @staticmethod
    def _sensitivity_summary(
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str | None,
    ) -> dict[str, Any]:
        totals: dict[str, int] = {}
        by_table: dict[str, dict[str, int]] = {}
        for table in _SENSITIVITY_TABLES:
            if not _table_exists(connection, table):
                continue
            columns = _table_columns(connection, table)
            if "sensitivity" not in columns or "owner_id" not in columns:
                continue
            clauses = ["owner_id=?"]
            params: list[Any] = [owner_id]
            if project_id and "project_id" in columns:
                clauses.append("project_id=?")
                params.append(project_id)
            rows = connection.execute(
                f'select sensitivity, count(*) from "{table}" '
                f"where {' and '.join(clauses)} group by sensitivity",
                params,
            ).fetchall()
            table_counts: dict[str, int] = {}
            for value, count in rows:
                label = str(value or "unspecified")[:64]
                table_counts[label] = int(count)
                totals[label] = totals.get(label, 0) + int(count)
            by_table[table] = table_counts
        return {"totals": totals, "by_table": by_table}
