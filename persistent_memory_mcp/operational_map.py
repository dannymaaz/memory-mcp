"""Bounded owner-scoped operational project map built from verified local evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .security import redact_sensitive_value
from .storage import SQLiteStorage

_MAX_PROJECTS = 100
_MAX_NODES = 500
_MAX_EDGES = 1500
_MAX_LABEL_CHARS = 120
_VERIFICATION_STATES = frozenset(
    {"verified", "stale", "contradicted", "missing_source", "unverified"}
)
_RISK_LEVELS = ("none", "low", "medium", "high", "critical")
_RISK_RANK = {value: index for index, value in enumerate(_RISK_LEVELS)}


@dataclass(frozen=True)
class OperationalMapLimits:
    """Hard bounds for one operational-map request."""

    max_projects: int = 50
    max_nodes: int = 250
    max_edges: int = 750
    max_records_per_kind: int = 50

    def __post_init__(self) -> None:
        checks = {
            "max_projects": (self.max_projects, 1, _MAX_PROJECTS),
            "max_nodes": (self.max_nodes, 1, _MAX_NODES),
            "max_edges": (self.max_edges, 0, _MAX_EDGES),
            "max_records_per_kind": (self.max_records_per_kind, 1, 200),
        }
        for name, (value, minimum, maximum) in checks.items():
            if not minimum <= int(value) <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")


@dataclass(frozen=True)
class OperationalNode:
    id: str
    kind: str
    label: str
    project_id: str
    status: str | None
    verification_state: str
    risk: str
    changed: bool = False
    stale: bool = False
    contradicted: bool = False
    missing_evidence: bool = False
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OperationalEdge:
    source: str
    target: str
    relation: str
    verification_state: str = "verified"
    confidence: float = 1.0


def _bounded_label(value: object, *, fallback: str) -> tuple[str, tuple[str, ...]]:
    text = " ".join(str(value or fallback).split())[:_MAX_LABEL_CHARS]
    redacted = redact_sensitive_value(text)
    return str(redacted.value), redacted.redactions


def _risk_for_state(state: str) -> str:
    return {
        "contradicted": "critical",
        "missing_source": "high",
        "stale": "high",
        "unverified": "medium",
        "verified": "none",
    }.get(state, "medium")


def _max_risk(*values: str) -> str:
    return max(values or ("none",), key=lambda value: _RISK_RANK.get(value, 2))


def _short_commit(value: object) -> str:
    return str(value or "")[:12]


def _repository_label(repository: object, project: Mapping[str, Any]) -> str:
    remote = str(project.get("repo_remote") or "").rstrip("/")
    if remote:
        name = remote.rsplit("/", 1)[-1].removesuffix(".git")
        if name:
            return name[:_MAX_LABEL_CHARS]
    value = str(repository or project.get("repo_path") or "repository")
    return Path(value).name[:_MAX_LABEL_CHARS] or "repository"


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


class OperationalMapService:
    """Compose compact operational state without returning full memory/source bodies."""

    def __init__(self, storage: SQLiteStorage, *, owner_id: str) -> None:
        self.storage = storage
        self.owner_id = owner_id.strip()
        if not self.owner_id:
            raise ValueError("owner_id is required for the operational map")

    @staticmethod
    def _validate_state_filter(verification: str | None, risk: str | None) -> None:
        if verification and verification not in _VERIFICATION_STATES:
            raise ValueError("unsupported verification state")
        if risk and risk not in _RISK_RANK:
            raise ValueError("unsupported risk level")

    def _projects(self, connection: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
        return _row_dicts(
            connection.execute(
                "select id, name, slug, repo_path, repo_remote, repo_branch, repo_last_commit, "
                "repo_status, updated_at from projects where owner_id=? "
                "order by updated_at desc, id asc limit ?",
                (self.owner_id, limit),
            ).fetchall()
        )

    @staticmethod
    def _latest_runs(connection: sqlite3.Connection, owner_id: str, project_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "select r.* from code_symbol_snapshot_runs r "
            "where r.owner_id=? and r.project_id=? and not exists ("
            "  select 1 from code_symbol_snapshot_runs newer "
            "  where newer.owner_id=r.owner_id and newer.project_id=r.project_id "
            "    and newer.repository=r.repository "
            "    and (newer.captured_at > r.captured_at "
            "      or (newer.captured_at = r.captured_at and newer.rowid > r.rowid))"
            ") order by r.repository asc",
            (owner_id, project_id),
        ).fetchall()
        return _row_dicts(rows)

    @staticmethod
    def _record_counts(connection: sqlite3.Connection, owner_id: str, project_id: str) -> dict[str, int]:
        active_tasks = int(
            connection.execute(
                "select count(*) from tasks where owner_id=? and project_id=? "
                "and lower(status) in ('pending','active','in_progress','blocked')",
                (owner_id, project_id),
            ).fetchone()[0]
        )
        blocked_tasks = int(
            connection.execute(
                "select count(*) from tasks where owner_id=? and project_id=? and lower(status)='blocked'",
                (owner_id, project_id),
            ).fetchone()[0]
        )
        active_warnings = int(
            connection.execute(
                "select count(*) from warnings where owner_id=? and project_id=? and is_active=1",
                (owner_id, project_id),
            ).fetchone()[0]
        )
        return {
            "active_tasks": active_tasks,
            "blocked_tasks": blocked_tasks,
            "active_warnings": active_warnings,
        }

    @staticmethod
    def _symbol_signals(
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str,
        runs: list[dict[str, Any]],
    ) -> dict[str, int]:
        if not runs:
            return {
                "changed_symbols": 0,
                "stale_evidence": 0,
                "contradicted_evidence": 0,
                "missing_evidence": 0,
                "unverified_evidence": 0,
            }
        run_ids = [str(run["id"]) for run in runs]
        placeholders = ",".join("?" for _ in run_ids)
        changed = int(
            connection.execute(
                f"select count(*) from code_symbol_changes where owner_id=? and project_id=? "
                f"and to_run_id in ({placeholders}) and change_type!='unchanged'",
                (owner_id, project_id, *run_ids),
            ).fetchone()[0]
        )
        states = {
            str(row[0]): int(row[1])
            for row in connection.execute(
                "select verification_state, count(*) from code_symbol_links "
                "where owner_id=? and project_id=? group by verification_state",
                (owner_id, project_id),
            ).fetchall()
        }
        return {
            "changed_symbols": changed,
            "stale_evidence": states.get("stale", 0),
            "contradicted_evidence": states.get("contradicted", 0),
            "missing_evidence": states.get("missing_source", 0),
            "unverified_evidence": states.get("unverified", 0),
        }

    def project_overview(
        self,
        *,
        limits: OperationalMapLimits | None = None,
        verification: str | None = None,
        risk: str | None = None,
    ) -> dict[str, Any]:
        """Return bounded project summaries for the active owner only."""
        active_limits = limits or OperationalMapLimits()
        self._validate_state_filter(verification, risk)
        summaries: list[dict[str, Any]] = []
        with self.storage.connect() as connection:
            projects = self._projects(connection, active_limits.max_projects)
            for project in projects:
                project_id = str(project["id"])
                runs = self._latest_runs(connection, self.owner_id, project_id)
                record_counts = self._record_counts(connection, self.owner_id, project_id)
                signals = self._symbol_signals(connection, self.owner_id, project_id, runs)
                verification_state = "verified"
                if signals["contradicted_evidence"]:
                    verification_state = "contradicted"
                elif signals["missing_evidence"]:
                    verification_state = "missing_source"
                elif signals["stale_evidence"]:
                    verification_state = "stale"
                elif signals["unverified_evidence"] or not runs:
                    verification_state = "unverified"

                project_risk = _risk_for_state(verification_state)
                if record_counts["blocked_tasks"]:
                    project_risk = _max_risk(project_risk, "high")
                warning_severity = connection.execute(
                    "select lower(severity) from warnings where owner_id=? and project_id=? and is_active=1 "
                    "order by case lower(severity) when 'critical' then 4 when 'high' then 3 "
                    "when 'medium' then 2 else 1 end desc limit 1",
                    (self.owner_id, project_id),
                ).fetchone()
                if warning_severity:
                    project_risk = _max_risk(
                        project_risk,
                        "critical" if warning_severity[0] == "critical" else "high" if warning_severity[0] == "high" else "medium",
                    )

                if verification and verification_state != verification:
                    continue
                if risk and project_risk != risk:
                    continue
                repo_status = project.get("repo_status")
                if isinstance(repo_status, str):
                    try:
                        repo_status = json.loads(repo_status)
                    except json.JSONDecodeError:
                        repo_status = {}
                summaries.append(
                    {
                        "project_id": project_id,
                        "name": str(project.get("name") or "Project")[:_MAX_LABEL_CHARS],
                        "slug": str(project.get("slug") or "")[:80],
                        "verification_state": verification_state,
                        "risk": project_risk,
                        "repository_count": len(runs) or int(bool(project.get("repo_path") or project.get("repo_remote"))),
                        "latest_commit": _short_commit(project.get("repo_last_commit") or (runs[0].get("commit_sha") if runs else "")),
                        "branch": str(project.get("repo_branch") or "")[:120],
                        "working_tree_dirty": bool((repo_status or {}).get("dirty")) if isinstance(repo_status, Mapping) else False,
                        **record_counts,
                        **signals,
                        "updated_at": project.get("updated_at"),
                    }
                )
        return {
            "projects": summaries,
            "counts": {
                "projects": len(summaries),
                "critical": sum(1 for item in summaries if item["risk"] == "critical"),
                "high": sum(1 for item in summaries if item["risk"] == "high"),
                "stale_or_worse": sum(
                    1
                    for item in summaries
                    if item["verification_state"] in {"stale", "contradicted", "missing_source"}
                ),
            },
            "filters": {"verification": verification, "risk": risk},
            "limits": asdict(active_limits),
            "read_only": True,
        }

    def impact_graph(
        self,
        project_id: str,
        *,
        limits: OperationalMapLimits | None = None,
        verification: str | None = None,
        risk: str | None = None,
        changed_only: bool = False,
    ) -> dict[str, Any]:
        """Return a bounded project → repo → file → symbol → memory operational graph."""
        active_limits = limits or OperationalMapLimits()
        self._validate_state_filter(verification, risk)
        nodes: dict[str, OperationalNode] = {}
        edges: list[OperationalEdge] = []
        redactions: set[str] = set()

        with self.storage.connect() as connection:
            project_row = connection.execute(
                "select id, name, slug, repo_path, repo_remote, repo_branch, repo_last_commit, repo_status "
                "from projects where id=? and owner_id=?",
                (project_id, self.owner_id),
            ).fetchone()
            if project_row is None:
                raise ValueError("project does not exist inside the active owner scope")
            project = dict(project_row)
            runs = self._latest_runs(connection, self.owner_id, project_id)
            latest_run_ids = {str(run["id"]) for run in runs}
            changed_logical_ids = {
                str(row[0])
                for row in connection.execute(
                    "select logical_id from code_symbol_changes where owner_id=? and project_id=? "
                    "and change_type!='unchanged' and to_run_id in (select id from code_symbol_snapshot_runs "
                    "where owner_id=? and project_id=?)",
                    (self.owner_id, project_id, self.owner_id, project_id),
                ).fetchall()
            }

            project_node_id = f"project:{project_id}"
            project_label, labels = _bounded_label(project.get("name"), fallback="Project")
            redactions.update(labels)
            nodes[project_node_id] = OperationalNode(
                id=project_node_id,
                kind="project",
                label=project_label,
                project_id=project_id,
                status=None,
                verification_state="verified" if runs else "unverified",
                risk="none" if runs else "medium",
                missing_evidence=not bool(runs),
                metadata={"slug": str(project.get("slug") or "")[:80]},
            )

            symbol_node_by_logical: dict[tuple[str, str], str] = {}
            file_nodes: dict[tuple[str, str], str] = {}
            for run in runs:
                repository = str(run.get("repository") or "")
                repo_key = f"repository:{project_id}:{run['id']}"
                repo_label, labels = _bounded_label(_repository_label(repository, project), fallback="Repository")
                redactions.update(labels)
                nodes[repo_key] = OperationalNode(
                    id=repo_key,
                    kind="repository",
                    label=repo_label,
                    project_id=project_id,
                    status=None,
                    verification_state="verified",
                    risk="none",
                    changed=False,
                    metadata={
                        "commit": _short_commit(run.get("commit_sha")),
                        "ref": str(run.get("ref") or "")[:120],
                        "symbol_count": int(run.get("symbol_count") or 0),
                    },
                )
                edges.append(OperationalEdge(project_node_id, repo_key, "tracks"))
                snapshots = connection.execute(
                    "select id, logical_id, path, name, qualified_name, kind, language, line, end_line, "
                    "verification_state from code_symbol_snapshots where run_id=? and owner_id=? and project_id=? "
                    "order by path asc, line asc, qualified_name asc limit ?",
                    (run["id"], self.owner_id, project_id, active_limits.max_nodes),
                ).fetchall()
                for snapshot_row in snapshots:
                    snapshot = dict(snapshot_row)
                    logical_id = str(snapshot["logical_id"])
                    changed = logical_id in changed_logical_ids
                    state = str(snapshot.get("verification_state") or "verified")
                    node_risk = _risk_for_state(state)
                    if changed_only and not changed:
                        continue
                    if verification and state != verification:
                        continue
                    if risk and node_risk != risk:
                        continue
                    path = str(snapshot["path"])
                    file_key = (repository, path)
                    file_node_id = file_nodes.get(file_key)
                    if not file_node_id:
                        file_node_id = f"file:{run['id']}:{path}"
                        file_nodes[file_key] = file_node_id
                        file_label, labels = _bounded_label(path, fallback="file")
                        redactions.update(labels)
                        nodes[file_node_id] = OperationalNode(
                            id=file_node_id,
                            kind="file",
                            label=file_label,
                            project_id=project_id,
                            status=None,
                            verification_state=state,
                            risk=node_risk,
                            changed=changed,
                            stale=state == "stale",
                            contradicted=state == "contradicted",
                            metadata={"path": path[:300]},
                        )
                        edges.append(OperationalEdge(repo_key, file_node_id, "contains", state))
                    symbol_node_id = f"symbol:{run['id']}:{logical_id}"
                    symbol_label, labels = _bounded_label(
                        snapshot.get("qualified_name") or snapshot.get("name"), fallback="symbol"
                    )
                    redactions.update(labels)
                    nodes[symbol_node_id] = OperationalNode(
                        id=symbol_node_id,
                        kind="symbol",
                        label=symbol_label,
                        project_id=project_id,
                        status=None,
                        verification_state=state,
                        risk=node_risk,
                        changed=changed,
                        stale=state == "stale",
                        contradicted=state == "contradicted",
                        metadata={
                            "logical_id": logical_id,
                            "path": path[:300],
                            "symbol_kind": str(snapshot.get("kind") or "")[:80],
                            "language": str(snapshot.get("language") or "")[:40],
                            "line": int(snapshot.get("line") or 0),
                            "end_line": int(snapshot.get("end_line") or 0),
                        },
                    )
                    symbol_node_by_logical[(repository, logical_id)] = symbol_node_id
                    edges.append(OperationalEdge(file_node_id, symbol_node_id, "defines", state))

            target_node_ids: dict[tuple[str, str], str] = {}
            record_specs = (
                ("task", "tasks", "title", "status", "priority"),
                ("decision", "decisions", "summary", None, "decision_type"),
                ("warning", "warnings", "message", None, "severity"),
            )
            for kind, table, label_column, status_column, signal_column in record_specs:
                select_columns = ["id", label_column, signal_column]
                if status_column:
                    select_columns.append(status_column)
                if table == "warnings":
                    select_columns.append("is_active")
                rows = connection.execute(
                    f"select {', '.join(select_columns)} from {table} where owner_id=? and project_id=? "
                    "order by rowid desc limit ?",
                    (self.owner_id, project_id, active_limits.max_records_per_kind),
                ).fetchall()
                for raw in rows:
                    row = dict(raw)
                    target_type = kind if kind in {"task", "decision"} else None
                    target_id = str(row["id"])
                    link_rows = []
                    if target_type:
                        link_rows = connection.execute(
                            "select repository, logical_id, relation_type, verification_state, confidence "
                            "from (select repository, logical_id, relation_type, verification_state, 1.0 as confidence "
                            "from code_symbol_links where owner_id=? and project_id=? and target_type=? and target_id=?) "
                            "order by verification_state asc, repository asc, logical_id asc",
                            (self.owner_id, project_id, target_type, target_id),
                        ).fetchall()
                    states = [str(item["verification_state"]) for item in link_rows]
                    state = "verified" if "verified" in states else states[0] if states else "unverified"
                    missing_evidence = target_type is not None and not link_rows
                    node_risk = _risk_for_state(state)
                    status = str(row.get(status_column) or "") if status_column else None
                    if kind == "task" and str(row.get("status") or "").casefold() == "blocked":
                        node_risk = _max_risk(node_risk, "high")
                    if kind == "warning" and bool(row.get("is_active")):
                        severity = str(row.get("severity") or "medium").casefold()
                        node_risk = _max_risk(
                            node_risk,
                            "critical" if severity == "critical" else "high" if severity == "high" else "medium",
                        )
                    if verification and state != verification:
                        continue
                    if risk and node_risk != risk:
                        continue
                    label, labels = _bounded_label(row.get(label_column), fallback=f"{kind} {target_id[:8]}")
                    redactions.update(labels)
                    node_id = f"{kind}:{target_id}"
                    target_node_ids[(kind, target_id)] = node_id
                    nodes[node_id] = OperationalNode(
                        id=node_id,
                        kind=kind,
                        label=label,
                        project_id=project_id,
                        status=status,
                        verification_state=state,
                        risk=node_risk,
                        stale=state == "stale",
                        contradicted=state == "contradicted",
                        missing_evidence=missing_evidence,
                        metadata={signal_column: str(row.get(signal_column) or "")[:80]},
                    )
                    edges.append(OperationalEdge(project_node_id, node_id, "contains", state))
                    for link in link_rows:
                        source = symbol_node_by_logical.get((str(link["repository"]), str(link["logical_id"])))
                        if source:
                            edges.append(
                                OperationalEdge(
                                    source,
                                    node_id,
                                    str(link["relation_type"] or "evidence_for"),
                                    str(link["verification_state"] or "unverified"),
                                    float(link["confidence"] or 1.0),
                                )
                            )

            link_rows = connection.execute(
                "select repository, logical_id, relation_type, target_type, target_id, verification_state "
                "from code_symbol_links where owner_id=? and project_id=? "
                "and target_type in ('file','test','deployment') order by rowid desc limit ?",
                (self.owner_id, project_id, active_limits.max_edges),
            ).fetchall()
            for link in link_rows:
                source = symbol_node_by_logical.get((str(link["repository"]), str(link["logical_id"])))
                if not source:
                    continue
                target_type = str(link["target_type"])
                target_label, labels = _bounded_label(link["target_id"], fallback=target_type)
                redactions.update(labels)
                target_id = f"evidence:{target_type}:{link['target_id']}"
                state = str(link["verification_state"] or "unverified")
                node_risk = _risk_for_state(state)
                if verification and state != verification:
                    continue
                if risk and node_risk != risk:
                    continue
                nodes.setdefault(
                    target_id,
                    OperationalNode(
                        id=target_id,
                        kind=target_type,
                        label=target_label,
                        project_id=project_id,
                        status=None,
                        verification_state=state,
                        risk=node_risk,
                        stale=state == "stale",
                        contradicted=state == "contradicted",
                        metadata=None,
                    ),
                )
                edges.append(
                    OperationalEdge(source, target_id, str(link["relation_type"] or "evidence_for"), state)
                )

        ordered_nodes = sorted(
            nodes.values(),
            key=lambda item: (
                -_RISK_RANK.get(item.risk, 2),
                not item.changed,
                item.kind,
                item.label.casefold(),
                item.id,
            ),
        )
        kept_ids = {node.id for node in ordered_nodes[: active_limits.max_nodes]}
        ordered_edges = sorted(
            (edge for edge in edges if edge.source in kept_ids and edge.target in kept_ids),
            key=lambda edge: (edge.relation, edge.source, edge.target),
        )[: active_limits.max_edges]
        final_nodes = [node for node in ordered_nodes[: active_limits.max_nodes]]
        risk_counts = {level: sum(1 for node in final_nodes if node.risk == level) for level in _RISK_LEVELS}
        state_counts = {
            state: sum(1 for node in final_nodes if node.verification_state == state)
            for state in sorted(_VERIFICATION_STATES)
        }
        return {
            "project_id": project_id,
            "nodes": [asdict(node) for node in final_nodes],
            "edges": [asdict(edge) for edge in ordered_edges],
            "summary": {
                "nodes": len(final_nodes),
                "edges": len(ordered_edges),
                "changed_nodes": sum(1 for node in final_nodes if node.changed),
                "missing_evidence_nodes": sum(1 for node in final_nodes if node.missing_evidence),
                "risk": risk_counts,
                "verification": state_counts,
            },
            "filters": {
                "verification": verification,
                "risk": risk,
                "changed_only": changed_only,
            },
            "limits": asdict(active_limits),
            "truncated": len(ordered_nodes) > active_limits.max_nodes or len(edges) > active_limits.max_edges,
            "redactions": sorted(redactions),
            "read_only": True,
        }
