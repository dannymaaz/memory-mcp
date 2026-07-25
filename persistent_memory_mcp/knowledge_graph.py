"""Bounded project knowledge graph construction for dashboard visualizations."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Sequence

MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 1500
MAX_CONTEXT_CHARS = 12000

_ENTITY_TABLES = {
    "projects": "project",
    "file_memory": "file",
    "memory_documents": "memory",
    "decisions": "decision",
    "tasks": "task",
    "warnings": "warning",
    "sessions": "session",
}

_OVERLAY_KEYS = {
    "duplicate_of": "duplicate_of",
    "duplicates": "duplicate_of",
    "contradicts": "contradicts",
    "contradicted_by": "contradicts",
}


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str
    label: str
    project_id: str | None
    status: str | None = None
    stale: bool = False
    contradicted: bool = False
    orphan: bool = False
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    confidence: float = 1.0


def _record_id(table: str, row: Mapping[str, Any]) -> str:
    raw = row.get("id") or row.get("file_path") or row.get("name") or row.get("title")
    return f"{table}:{raw}"


def _label(table: str, row: Mapping[str, Any]) -> str:
    for key in ("name", "title", "file_path", "summary", "session_id", "id"):
        value = row.get(key)
        if value:
            return str(value)[:160]
    return table


def _matches(row: Mapping[str, Any], query: str) -> bool:
    if not query:
        return True
    return query.casefold() in json.dumps(row, ensure_ascii=False, default=str).casefold()


def _status_flags(row: Mapping[str, Any]) -> tuple[bool, bool]:
    verification = str(row.get("verification_status") or row.get("status") or "").casefold()
    return verification == "stale", verification == "contradicted"


def _decoded_metadata(row: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = row.get("metadata")
    if isinstance(raw, Mapping):
        return raw
    if isinstance(raw, str) and raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, Mapping):
            return decoded
    return {}


def _reference_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        raw = value.get("node_id") or value.get("id")
        return [str(raw)] if raw else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        result: list[str] = []
        for item in value:
            result.extend(_reference_values(item))
        return result
    return [str(value)]


def _symbol_names(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("symbols")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = [raw]
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            value = item.get("qualified_name") or item.get("name") or item.get("id")
        else:
            value = item
        if value:
            names.append(str(value)[:160])
    return list(dict.fromkeys(names))[:100]


def _resolve_overlay_target(reference: str, table: str, node_ids: set[str]) -> str | None:
    candidates = (reference, f"{table}:{reference}")
    for candidate in candidates:
        if candidate in node_ids:
            return candidate
    return None


def build_knowledge_graph(
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    project_id: str | None = None,
    query: str = "",
    max_nodes: int = 250,
    max_edges: int = 750,
) -> dict[str, Any]:
    """Build a deterministic, bounded graph from dashboard-compatible table rows."""
    if not 1 <= max_nodes <= MAX_GRAPH_NODES:
        raise ValueError(f"max_nodes must be between 1 and {MAX_GRAPH_NODES}")
    if not 0 <= max_edges <= MAX_GRAPH_EDGES:
        raise ValueError(f"max_edges must be between 0 and {MAX_GRAPH_EDGES}")
    if len(query) > 200:
        raise ValueError("query must be at most 200 characters")

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    project_nodes: dict[str, str] = {}
    file_nodes: dict[tuple[str | None, str], str] = {}
    overlay_requests: list[tuple[str, str, str, str]] = []

    for row in tables.get("projects", ()):
        if project_id and str(row.get("id")) != project_id:
            continue
        node_id = _record_id("projects", row)
        project_key = str(row.get("id") or "")
        project_nodes[project_key] = node_id
        stale, contradicted = _status_flags(row)
        nodes[node_id] = GraphNode(
            id=node_id,
            kind="project",
            label=_label("projects", row),
            project_id=project_key or None,
            status=str(row.get("status")) if row.get("status") else None,
            stale=stale,
            contradicted=contradicted,
            metadata={"slug": row.get("slug")},
        )

    for table, kind in _ENTITY_TABLES.items():
        if table == "projects":
            continue
        for row in tables.get(table, ()):
            row_project = str(row.get("project_id") or "") or None
            if project_id and row_project != project_id:
                continue
            if not _matches(row, query):
                continue
            node_id = _record_id(table, row)
            stale, contradicted = _status_flags(row)
            metadata = _decoded_metadata(row)
            nodes[node_id] = GraphNode(
                id=node_id,
                kind=kind,
                label=_label(table, row),
                project_id=row_project,
                status=str(row.get("status")) if row.get("status") else None,
                stale=stale,
                contradicted=contradicted,
                metadata={"source_table": table},
            )
            for key, relation in _OVERLAY_KEYS.items():
                for reference in _reference_values(metadata.get(key)):
                    overlay_requests.append((node_id, table, relation, reference))
            if table == "file_memory" and row.get("file_path"):
                file_nodes[(row_project, str(row["file_path"]))] = node_id
                for index, symbol_name in enumerate(_symbol_names(row)):
                    symbol_id = f"symbol:{node_id}:{index}:{symbol_name}"
                    nodes[symbol_id] = GraphNode(
                        id=symbol_id,
                        kind="symbol",
                        label=symbol_name,
                        project_id=row_project,
                        metadata={"file_node": node_id, "file_path": row.get("file_path")},
                    )
                    edges.append(GraphEdge(node_id, symbol_id, "defines"))
            project_node = project_nodes.get(row_project or "")
            if project_node:
                edges.append(GraphEdge(project_node, node_id, "contains"))

    for row in tables.get("file_relations", ()):
        relation_project = str(row.get("project_id") or "") or None
        if project_id and relation_project != project_id:
            continue
        source = file_nodes.get((relation_project, str(row.get("source_file") or "")))
        target = file_nodes.get((relation_project, str(row.get("target_file") or "")))
        if source and target:
            edges.append(
                GraphEdge(
                    source,
                    target,
                    str(row.get("relation_type") or "related"),
                    float(row.get("confidence") or 1.0),
                )
            )

    node_ids = set(nodes)
    overlay_counts = {"duplicate_of": 0, "contradicts": 0}
    seen_overlays: set[tuple[str, str, str]] = set()
    for source, table, relation, reference in overlay_requests:
        target = _resolve_overlay_target(reference, table, node_ids)
        if not target or target == source:
            continue
        edge_key = (source, target, relation)
        if edge_key in seen_overlays:
            continue
        seen_overlays.add(edge_key)
        edges.append(GraphEdge(source, target, relation))
        overlay_counts[relation] += 1
        if relation == "contradicts":
            nodes[source] = replace(nodes[source], contradicted=True)
            nodes[target] = replace(nodes[target], contradicted=True)

    ordered_nodes = sorted(nodes.values(), key=lambda item: (item.kind, item.label.casefold(), item.id))
    kept = {item.id for item in ordered_nodes[:max_nodes]}
    ordered_edges = sorted(
        (edge for edge in edges if edge.source in kept and edge.target in kept),
        key=lambda item: (item.relation, item.source, item.target),
    )[:max_edges]
    connected = {edge.source for edge in ordered_edges} | {edge.target for edge in ordered_edges}
    final_nodes = [
        GraphNode(**{**asdict(node), "orphan": node.id not in connected})
        for node in ordered_nodes[:max_nodes]
    ]
    return {
        "nodes": [asdict(node) for node in final_nodes],
        "edges": [asdict(edge) for edge in ordered_edges],
        "overlays": overlay_counts,
        "limits": {"max_nodes": max_nodes, "max_edges": max_edges},
        "truncated": len(ordered_nodes) > max_nodes or len(edges) > max_edges,
    }


def focus_subgraph(
    graph: Mapping[str, Sequence[Mapping[str, Any]]],
    node_ids: Sequence[str],
    *,
    depth: int = 1,
    max_nodes: int = 100,
) -> dict[str, Any]:
    """Return a compact neighborhood around explicitly selected nodes."""
    if not 0 <= depth <= 4:
        raise ValueError("depth must be between 0 and 4")
    if not 1 <= max_nodes <= MAX_GRAPH_NODES:
        raise ValueError(f"max_nodes must be between 1 and {MAX_GRAPH_NODES}")
    nodes = {str(node["id"]): dict(node) for node in graph.get("nodes", ())}
    edges = [dict(edge) for edge in graph.get("edges", ())]
    selected = [node_id for node_id in dict.fromkeys(node_ids) if node_id in nodes]
    visited = set(selected)
    queue = deque((node_id, 0) for node_id in selected)
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        source, target = str(edge["source"]), str(edge["target"])
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)
    while queue and len(visited) < max_nodes:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for neighbor in sorted(adjacency.get(current, ())):
            if neighbor not in visited and len(visited) < max_nodes:
                visited.add(neighbor)
                queue.append((neighbor, current_depth + 1))
    return {
        "nodes": [nodes[node_id] for node_id in sorted(visited)],
        "edges": [edge for edge in edges if edge["source"] in visited and edge["target"] in visited],
        "selection": selected,
        "depth": depth,
    }


def compact_graph_context(
    graph: Mapping[str, Sequence[Mapping[str, Any]]],
    node_ids: Sequence[str],
    *,
    depth: int = 1,
    max_nodes: int = 50,
    max_chars: int = 6000,
) -> dict[str, Any]:
    """Build deterministic, bounded, read-only context from an explicit graph selection."""
    if not 1 <= max_chars <= MAX_CONTEXT_CHARS:
        raise ValueError(f"max_chars must be between 1 and {MAX_CONTEXT_CHARS}")
    focused = focus_subgraph(graph, node_ids, depth=depth, max_nodes=max_nodes)
    lines: list[str] = []
    for node in focused["nodes"]:
        flags = [name for name in ("stale", "contradicted", "orphan") if node.get(name)]
        suffix = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- {node.get('kind')}: {node.get('label')}{suffix}")
    for edge in focused["edges"]:
        lines.append(f"- relation: {edge.get('source')} --{edge.get('relation')}--> {edge.get('target')}")
    text = "\n".join(lines)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars].rstrip()
    return {
        **focused,
        "context": text,
        "truncated": truncated,
        "read_only": True,
    }
