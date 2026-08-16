"""Bounded owner-scoped operational project map built from verified local evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .security import redact_sensitive_value
from .storage import SQLiteStorage

_MAX_PROJECTS = 100
_MAX_REPOSITORIES = 20
_MAX_NODES = 500
_MAX_EDGES = 1500
_MAX_LABEL_CHARS = 120
_VERIFICATION_STATES = frozenset(
    {"verified", "stale", "contradicted", "missing_source", "unverified"}
)
_RISK_LEVELS = ("none", "low", "medium", "high", "critical")
_RISK_RANK = {value: index for index, value in enumerate(_RISK_LEVELS)}
_KIND_ORDER = {
    "project": 0,
    "repository": 1,
    "warning": 2,
    "task": 3,
    "decision": 4,
    "file": 5,
    "symbol": 6,
    "test": 7,
    "deployment": 8,
}


@dataclass(frozen=True)
class OperationalMapLimits:
    """Hard bounds for one operational-map request."""

    max_projects: int = 50
    max_repositories: int = 12
    max_nodes: int = 250
    max_edges: int = 750
    max_records_per_kind: int = 50

    def __post_init__(self) -> None:
        checks = {
            "max_projects": (self.max_projects, 1, _MAX_PROJECTS),
            "max_repositories": (self.max_repositories, 1, _MAX_REPOSITORIES),
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


def _worst_state(states: list[str]) -> str:
    for state in ("contradicted", "missing_source", "stale", "unverified", "verified"):
        if state in states:
            return state
    return "unverified"


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
    def _latest_runs(
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "select r.* from code_symbol_snapshot_runs r "
            "where r.owner_id=? and r.project_id=? and not exists ("
            "  select 1 from code_symbol_snapshot_runs newer "
            "  where newer.owner_id=r.owner_id and newer.project_id=r.project_id "
            "    and newer.repository=r.repository "
            "    and (newer.captured_at > r.captured_at "
            "      or (newer.captured_at = r.captured_at and newer.rowid > r.rowid))"
            ") order by r.repository asc limit ?",
            (owner_id, project_id, limit),
        ).fetchall()
        return _row_dicts(rows)

    @staticmethod
    def _current_changed_ids(
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str,
        runs: list[dict[str, Any]],
    ) -> set[str]:
        if not runs:
            return set()
        run_ids = [str(run["id"]) for run in runs]
        placeholders = ",".join("?" for _ in run_ids)
        rows = connection.execute(
            f"select distinct logical_id from code_symbol_changes where owner_id=? and project_id=? "
            f"and to_run_id in ({placeholders}) and change_type!='unchanged'",
            (owner_id, project_id, *run_ids),
        ).fetchall()
        return {str(row[0]) for row in rows}

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

    @classmethod
    def _symbol_signals(
        cls,
        connection: sqlite3.Connection,
        owner_id: str,
        project_id: str,
        runs: list[dict[str, Any]],
    ) -> dict[str, int]:
        changed = len(cls._current_changed_ids(connection, owner_id, project_id, runs))
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
        redactions: set[str] = set()
        with self.storage.connect() as connection:
            projects = self._projects(connection, active_limits.max_projects)
            for project in projects:
                project_id = str(project["id"])
                runs = self._latest_runs(
                    connection, self.owner_id, project_id, active_limits.max_repositories
                )
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
                    severity = str(warning_severity[0])
                    project_risk = _max_risk(
                        project_risk,
                        "critical" if severity == "critical" else "high" if severity == "high" else "medium",
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
                name, labels = _bounded_label(project.get("name"), fallback="Project")
                redactions.update(labels)
                summaries.append(
                    {
                        "project_id": project_id,
                        "name": name,
                        "slug": str(project.get("slug") or "")[:80],
                        "verification_state": verification_state,
                        "risk": project_risk,
                        "repository_count": len(runs)
                        or int(bool(project.get("repo_path") or project.get("repo_remote"))),
                        "latest_commit": _short_commit(
                            project.get("repo_last_commit")
                            or (runs[0].get("commit_sha") if runs else "")
                        ),
                        "branch": str(project.get("repo_branch") or "")[:120],
                        "working_tree_dirty": bool((repo_status or {}).get("dirty"))
                        if isinstance(repo_status, Mapping)
                        else False,
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
            "redactions": sorted(redactions),
            "read_only": True,
        }

    @staticmethod
    def _node_matches(node: OperationalNode, verification: str | None, risk: str | None) -> bool:
        return (not verification or node.verification_state == verification) and (
            not risk or node.risk == risk
        )

    @staticmethod
    def _filter_changed_area(
        nodes: dict[str, OperationalNode],
        edges: list[OperationalEdge],
    ) -> tuple[dict[str, OperationalNode], list[OperationalEdge]]:
        changed = {
            node_id
            for node_id, node in nodes.items()
            if node.changed and node.kind in {"file", "symbol"}
        }
        if not changed:
            anchors = {node_id for node_id, node in nodes.items() if node.kind == "project"}
            return {node_id: nodes[node_id] for node_id in anchors}, []

        selected = set(changed)
        for edge in edges:
            if edge.source in changed or edge.target in changed:
                selected.add(edge.source)
                selected.add(edge.target)
        for relation in ("defines", "contains", "tracks"):
            progressed = True
            while progressed:
                progressed = False
                for edge in edges:
                    if edge.relation == relation and edge.target in selected and edge.source not in selected:
                        selected.add(edge.source)
                        progressed = True
        return (
            {node_id: node for node_id, node in nodes.items() if node_id in selected},
            [edge for edge in edges if edge.source in selected and edge.target in selected],
        )

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
            runs = self._latest_runs(
                connection, self.owner_id, project_id, active_limits.max_repositories
            )
            changed_logical_ids = self._current_changed_ids(
                connection, self.owner_id, project_id, runs
            )

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
            file_node_by_key: dict[tuple[str, str], str] = {}
            repo_node_by_repository: dict[str, str] = {}
            for run in runs:
                repository = str(run.get("repository") or "")
                repo_key = f"repository:{project_id}:{run['id']}"
                repo_node_by_repository[repository] = repo_key
                repo_label, labels = _bounded_label(
                    _repository_label(repository, project), fallback="Repository"
                )
                redactions.update(labels)
                nodes[repo_key] = OperationalNode(
                    id=repo_key,
                    kind="repository",
                    label=repo_label,
                    project_id=project_id,
                    status=None,
                    verification_state="verified",
                    risk="none",
                    metadata={
                        "commit": _short_commit(run.get("commit_sha")),
                        "ref": str(run.get("ref") or "")[:120],
                        "symbol_count": int(run.get("symbol_count") or 0),
                    },
                )
                edges.append(OperationalEdge(project_node_id, repo_key, "tracks"))
                snapshots = connection.execute(
                    "select logical_id, path, name, qualified_name, kind, language, line, end_line, "
                    "verification_state from code_symbol_snapshots "
                    "where run_id=? and owner_id=? and project_id=? "
                    "order by path asc, line asc, qualified_name asc limit ?",
                    (run["id"], self.owner_id, project_id, active_limits.max_nodes),
                ).fetchall()
                for snapshot_row in snapshots:
                    snapshot = dict(snapshot_row)
                    logical_id = str(snapshot["logical_id"])
                    changed = logical_id in changed_logical_ids
                    state = str(snapshot.get("verification_state") or "verified")
                    node_risk = _risk_for_state(state)
                    path = str(snapshot["path"])
                    file_key = (repository, path)
                    file_node_id = file_node_by_key.get(file_key)
                    if not file_node_id:
                        file_node_id = f"file:{run['id']}:{path}"
                        file_node_by_key[file_key] = file_node_id
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
                    elif changed and not nodes[file_node_id].changed:
                        nodes[file_node_id] = replace(nodes[file_node_id], changed=True)

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

            raw_links = connection.execute(
                "select repository, logical_id, relation_type, target_type, target_id, target_ref, "
                "verification_state from code_symbol_links where owner_id=? and project_id=? "
                "order by updated_at desc, rowid desc limit ?",
                (self.owner_id, project_id, min(active_limits.max_edges * 2 + 20, 3000)),
            ).fetchall()
            links = [dict(row) for row in raw_links]
            links_by_target: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for link in links:
                links_by_target.setdefault(
                    (str(link["target_type"]), str(link["target_id"])), []
                ).append(link)

            record_specs = (
                ("task", "tasks", "title", "status", "priority"),
                ("decision", "decisions", "summary", None, "decision_type"),
                ("warning", "warnings", "message", None, "severity"),
            )
            for kind, table, label_column, status_column, signal_column in record_specs:
                columns = ["id", label_column, signal_column]
                if status_column:
                    columns.append(status_column)
                if table == "warnings":
                    columns.append("is_active")
                rows = connection.execute(
                    f"select {', '.join(columns)} from {table} where owner_id=? and project_id=? "
                    "order by rowid desc limit ?",
                    (self.owner_id, project_id, active_limits.max_records_per_kind),
                ).fetchall()
                for raw in rows:
                    row = dict(raw)
                    target_id = str(row["id"])
                    target_links = links_by_target.get((kind, target_id), []) if kind != "warning" else []
                    states = [str(link["verification_state"]) for link in target_links]
                    state = _worst_state(states) if states else ("verified" if kind == "warning" else "unverified")
                    missing_evidence = kind in {"task", "decision"} and not target_links
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
                    label, labels = _bounded_label(
                        row.get(label_column), fallback=f"{kind} {target_id[:8]}"
                    )
                    redactions.update(labels)
                    node_id = f"{kind}:{target_id}"
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
                    for link in target_links:
                        source = symbol_node_by_logical.get(
                            (str(link["repository"]), str(link["logical_id"]))
                        )
                        if source:
                            edges.append(
                                OperationalEdge(
                                    source,
                                    node_id,
                                    str(link["relation_type"] or "evidence_for"),
                                    str(link["verification_state"] or "unverified"),
                                )
                            )

            for link in links:
                target_type = str(link["target_type"])
                if target_type not in {"file", "test", "deployment"}:
                    continue
                source = symbol_node_by_logical.get(
                    (str(link["repository"]), str(link["logical_id"]))
                )
                if not source:
                    continue
                state = str(link["verification_state"] or "unverified")
                target_raw = str(link.get("target_ref") or link["target_id"])
                if target_type == "file":
                    existing = file_node_by_key.get((str(link["repository"]), target_raw))
                    if existing:
                        edges.append(
                            OperationalEdge(
                                source,
                                existing,
                                str(link["relation_type"] or "defined_in"),
                                state,
                            )
                        )
                        continue
                target_label, labels = _bounded_label(target_raw, fallback=target_type)
                redactions.update(labels)
                target_id = f"evidence:{target_type}:{link['target_id']}"
                nodes.setdefault(
                    target_id,
                    OperationalNode(
                        id=target_id,
                        kind=target_type,
                        label=target_label,
                        project_id=project_id,
                        status=None,
                        verification_state=state,
                        risk=_risk_for_state(state),
                        stale=state == "stale",
                        contradicted=state == "contradicted",
                        metadata=None,
                    ),
                )
                edges.append(
                    OperationalEdge(
                        source,
                        target_id,
                        str(link["relation_type"] or "evidence_for"),
                        state,
                    )
                )

        for repository, repo_node_id in repo_node_by_repository.items():
            child_ids = [
                file_id for (repo, _), file_id in file_node_by_key.items() if repo == repository
            ]
            if child_ids:
                state = _worst_state([nodes[file_id].verification_state for file_id in child_ids])
                nodes[repo_node_id] = replace(
                    nodes[repo_node_id],
                    verification_state=state,
                    risk=_risk_for_state(state),
                    stale=state == "stale",
                    contradicted=state == "contradicted",
                    changed=any(nodes[file_id].changed for file_id in child_ids),
                )
        child_nodes = [node for node_id, node in nodes.items() if node_id != project_node_id]
        if child_nodes:
            state = _worst_state([node.verification_state for node in child_nodes])
            nodes[project_node_id] = replace(
                nodes[project_node_id],
                verification_state=state,
                risk=max(
                    (node.risk for node in child_nodes),
                    key=lambda item: _RISK_RANK.get(item, 2),
                ),
                stale=state == "stale",
                contradicted=state == "contradicted",
                changed=any(node.changed for node in child_nodes),
            )

        if changed_only:
            nodes, edges = self._filter_changed_area(nodes, edges)

        if verification or risk:
            matching = {
                node_id
                for node_id, node in nodes.items()
                if self._node_matches(node, verification, risk)
            }
            selected = set(matching)
            for edge in edges:
                if edge.source in matching or edge.target in matching:
                    selected.add(edge.source)
                    selected.add(edge.target)
            nodes = {node_id: node for node_id, node in nodes.items() if node_id in selected}
            edges = [edge for edge in edges if edge.source in nodes and edge.target in nodes]

        ordered_nodes = sorted(
            nodes.values(),
            key=lambda item: (
                item.kind != "project",
                -_RISK_RANK.get(item.risk, 2),
                _KIND_ORDER.get(item.kind, 99),
                not item.changed,
                item.label.casefold(),
                item.id,
            ),
        )
        kept_ids = {node.id for node in ordered_nodes[: active_limits.max_nodes]}
        ordered_edges = sorted(
            (edge for edge in edges if edge.source in kept_ids and edge.target in kept_ids),
            key=lambda edge: (edge.relation, edge.source, edge.target),
        )[: active_limits.max_edges]
        final_nodes = ordered_nodes[: active_limits.max_nodes]
        risk_counts = {
            level: sum(1 for node in final_nodes if node.risk == level) for level in _RISK_LEVELS
        }
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
            "truncated": len(ordered_nodes) > active_limits.max_nodes
            or len(edges) > active_limits.max_edges,
            "redactions": sorted(redactions),
            "read_only": True,
        }
