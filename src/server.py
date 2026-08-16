"""Servidor MCP para memoria persistente multi-interfaz con Supabase."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Callable

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import Json, RealDictCursor
except ModuleNotFoundError:  # pragma: no cover - optional direct SQL path
    psycopg2 = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]
    Json = None  # type: ignore[assignment]
    RealDictCursor = None  # type: ignore[assignment]

from mcp.server import MCPServer

from .interface_detector import detect_interface, get_model_for_interface
from .model_router import ModelRouter
from .optimizer import ContextOptimizer
from .utils import (
    detect_repo_context,
    derive_workspace_slug,
    format_context,
    format_decision,
    get_supabase_client,
    set_owner_context,
    slugify,
    validate_project_id,
    validate_severity,
)

Handler = Callable[..., Any]

server = MCPServer(
    name="Memory MCP",
    instructions=(
        "Persistent project memory MCP server backed by Supabase. "
        "Use tools to resolve or create projects automatically, persist decisions, "
        "track file memory, sync sessions, run semantic search, manage checkpoints, "
        "and resume work across AI clients."
    ),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)
optimizer = ContextOptimizer()
router = ModelRouter()

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "resolve_project", "description": "Resuelve o crea un proyecto automaticamente."},
    {"name": "create_project", "description": "Crea un proyecto con metadata de repo y workspace."},
    {"name": "list_projects", "description": "Lista proyectos del owner o workspace actual."},
    {"name": "load_unified_context", "description": "Carga contexto persistente optimizado."},
    {"name": "save_cross_interface_decision", "description": "Guarda decisiones compartidas."},
    {"name": "update_task_status", "description": "Crea o actualiza tareas del proyecto."},
    {"name": "create_session", "description": "Crea una sesion y guarda contexto git."},
    {"name": "end_session", "description": "Finaliza una sesion y genera resumen automatico."},
    {"name": "add_warning", "description": "Registra advertencias inteligentes."},
    {"name": "get_active_warnings", "description": "Lista advertencias activas."},
    {"name": "sync_session_state", "description": "Sincroniza el estado de sesion."},
    {"name": "get_interface_analytics", "description": "Resume uso por interfaz."},
    {"name": "save_file_memory", "description": "Guarda memoria por archivo y relaciones."},
    {"name": "save_checkpoint", "description": "Guarda checkpoints de arquitectura y estado."},
    {"name": "save_prompt_pattern", "description": "Guarda prompts utiles y patrones de respuesta."},
    {"name": "capture_project_memory", "description": "Guarda automaticamente decisiones, tareas, checkpoints, archivos y estado en una sola llamada."},
    {"name": "search_semantic_memory", "description": "Busca memoria por significado o texto."},
    {"name": "get_project_timeline", "description": "Devuelve la linea de tiempo del proyecto."},
    {"name": "export_memory_bundle", "description": "Exporta memoria a JSON o Markdown."},
    {"name": "import_memory_bundle", "description": "Importa memoria desde JSON o diccionario."},
    {"name": "resume_project", "description": "Devuelve un resumen listo para retomar el proyecto."},
    {"name": "apply_retention_policy", "description": "Aplica politicas de retencion y archivo."},
]


def _now_iso() -> str:
    """Retorna un timestamp ISO UTC."""
    return datetime.now(UTC).isoformat()


def _normalize_text(value: str) -> str:
    """Normaliza texto para comparaciones sencillas."""
    return " ".join(str(value).strip().lower().split())


def _ensure_list(value: Any) -> list[Any]:
    """Convierte un valor opcional en lista."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_json(value: Any) -> Any:
    """Normaliza estructuras para serializacion y Supabase."""
    if value is None:
        return {}
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.loads(json.dumps(value, default=str))


def _client(owner_id: str | None = None) -> Any:
    """Crea cliente y aplica contexto de propietario si existe."""
    client = get_supabase_client()
    resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
    return set_owner_context(client, resolved_owner)


def _use_database_url() -> bool:
    """Indica si debe usarse acceso SQL directo en lugar de PostgREST."""
    return bool(os.getenv("DATABASE_URL")) and psycopg2 is not None


def _db_connect() -> Any:
    """Crea una conexion Postgres directa cuando DATABASE_URL esta disponible."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for direct database access")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(database_url, sslmode="require")


def _db_prepare_value(value: Any) -> Any:
    """Convierte valores Python a formatos compatibles con psycopg2."""
    if Json is not None and isinstance(value, (dict, list)):
        return Json(value)
    return value


def _db_conflict_columns(table: str, payload: dict[str, Any]) -> list[str] | None:
    """Retorna columnas de conflicto para UPSERT directo."""
    if payload.get("id"):
        return ["id"]
    mapping = {
        "workspaces": ["owner_id", "slug"],
        "projects": ["slug"],
        "preferences": ["project_id", "preference_key"],
        "session_state": ["session_id"],
        "file_memory": ["project_id", "file_path"],
        "file_relations": ["project_id", "source_file", "target_file", "relation_type"],
        "prompt_patterns": ["project_id", "title"],
        "retention_policies": ["project_id"],
    }
    conflict = mapping.get(table)
    if conflict and all(column in payload and payload[column] is not None for column in conflict):
        return conflict
    return None


def _db_select(table: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Lee filas por SQL directo."""
    assert sql is not None and RealDictCursor is not None
    with _db_connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = sql.SQL("select * from {}").format(sql.Identifier(table))
            values: list[Any] = []
            if filters:
                clauses = []
                for key, value in filters.items():
                    clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                    values.append(value)
                query += sql.SQL(" where ") + sql.SQL(" and ").join(clauses)
            cursor.execute(query, values)
            rows = cursor.fetchall()
            return [_safe_json(dict(row)) for row in rows]


def _db_insert(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Inserta una fila por SQL directo y retorna el registro."""
    assert sql is not None and RealDictCursor is not None
    clean_payload = {key: value for key, value in payload.items() if value is not None}
    columns = list(clean_payload.keys())
    values = [_db_prepare_value(clean_payload[column]) for column in columns]
    with _db_connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = sql.SQL("insert into {} ({}) values ({}) returning *").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.SQL("%s") for _ in columns),
            )
            cursor.execute(query, values)
            row = cursor.fetchone()
            connection.commit()
            return _safe_json(dict(row)) if row else _safe_json(clean_payload)


def _db_upsert(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Hace UPSERT por SQL directo o inserta cuando no hay conflicto definido."""
    assert sql is not None and RealDictCursor is not None
    clean_payload = {key: value for key, value in payload.items() if value is not None}
    conflict_columns = _db_conflict_columns(table, clean_payload)
    if conflict_columns is None:
        return _db_insert(table, clean_payload)

    columns = list(clean_payload.keys())
    values = [_db_prepare_value(clean_payload[column]) for column in columns]
    update_columns = [column for column in columns if column not in conflict_columns]
    if not update_columns:
        update_columns = [conflict_columns[0]]

    with _db_connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = sql.SQL(
                "insert into {} ({}) values ({}) on conflict ({}) do update set {} returning *"
            ).format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.SQL("%s") for _ in columns),
                sql.SQL(", ").join(sql.Identifier(column) for column in conflict_columns),
                sql.SQL(", ").join(
                    sql.SQL("{} = excluded.{}").format(
                        sql.Identifier(column),
                        sql.Identifier(column),
                    )
                    for column in update_columns
                ),
            )
            cursor.execute(query, values)
            row = cursor.fetchone()
            connection.commit()
            return _safe_json(dict(row)) if row else _safe_json(clean_payload)


def _extract_data(response: Any) -> Any:
    """Normaliza la forma de leer respuestas del cliente Supabase."""
    return getattr(response, "data", response)


def _table_select(client: Any, table: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Consulta una tabla con filtros simples de igualdad."""
    if _use_database_url():
        return _db_select(table, filters)
    query = client.table(table).select("*")
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    result = _extract_data(query.execute())
    return result if isinstance(result, list) else []


def _table_upsert(client: Any, table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Inserta o actualiza un registro en Supabase y retorna una fila."""
    if _use_database_url():
        return _db_upsert(table, payload)
    result = _extract_data(client.table(table).upsert(payload).execute())
    if isinstance(result, list) and result:
        return result[0]
    if isinstance(result, dict):
        return result
    return payload


def _table_insert(client: Any, table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Inserta un registro nuevo en Supabase y retorna una fila."""
    if _use_database_url():
        return _db_insert(table, payload)
    result = _extract_data(client.table(table).insert(payload).execute())
    if isinstance(result, list) and result:
        return result[0]
    if isinstance(result, dict):
        return result
    return payload


def _table_rpc(client: Any, function_name: str, params: dict[str, Any]) -> Any:
    """Ejecuta una funcion RPC si el cliente la soporta."""
    if _use_database_url() and function_name == "match_memory_documents":
        assert RealDictCursor is not None
        with _db_connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    (
                        "select * from match_memory_documents(%s::vector, %s, %s::uuid, %s)"
                    ),
                    [
                        str(params.get("query_embedding", [])),
                        params.get("match_count", 5),
                        params.get("filter_project_id"),
                        params.get("filter_owner_id"),
                    ],
                )
                return [_safe_json(dict(row)) for row in cursor.fetchall()]
    if not hasattr(client, "rpc"):
        return []
    response = client.rpc(function_name, params).execute()
    return _extract_data(response)


def _sort_rows(rows: list[dict[str, Any]], key: str = "created_at", reverse: bool = True) -> list[dict[str, Any]]:
    """Ordena filas por una clave sin fallar si falta el valor."""
    return sorted(rows, key=lambda row: str(row.get(key, "")), reverse=reverse)


def _record_timeline(
    client: Any,
    project_id: str,
    owner_id: str,
    event_type: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Registra un evento de timeline y tambien lo refleja en interface_logs."""
    timeline_payload = {
        "project_id": project_id,
        "owner_id": owner_id,
        "event_type": event_type,
        "summary": summary,
        "payload": _safe_json(payload or {}),
        "created_at": _now_iso(),
    }
    event = _table_insert(client, "timeline_events", timeline_payload)
    _table_insert(
        client,
        "interface_logs",
        {
            "project_id": project_id,
            "owner_id": owner_id,
            "interface": payload.get("interface", "system") if payload else "system",
            "event_name": event_type,
            "payload": _safe_json(payload or {}),
            "latency_ms": 0,
            "created_at": _now_iso(),
        },
    )
    return event


def _upsert_memory_document(
    client: Any,
    project_id: str,
    owner_id: str,
    source_type: str,
    source_id: str,
    title: str,
    content: str,
    keywords: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Guarda un documento indexable para busquedas y exportes."""
    payload = {
        "project_id": project_id,
        "owner_id": owner_id,
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "content": content,
        "keywords": keywords or [],
        "metadata": _safe_json(metadata or {}),
    }
    if embedding:
        payload["embedding"] = embedding
    return _table_upsert(client, "memory_documents", payload)


def _ensure_workspace(
    client: Any,
    owner_id: str,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    repo_remote: str = "",
) -> dict[str, Any]:
    """Resuelve o crea un workspace estable para el owner actual."""
    if workspace_id:
        rows = _table_select(client, "workspaces", {"id": workspace_id})
        if rows:
            return rows[0]

    workspace_slug = derive_workspace_slug(owner_id, repo_remote)
    rows = _table_select(client, "workspaces", {"owner_id": owner_id, "slug": workspace_slug})
    if rows:
        return rows[0]

    payload = {
        "owner_id": owner_id,
        "slug": workspace_slug,
        "name": workspace_name or workspace_slug.replace("-", " ").title(),
        "description": "Auto-created workspace for Memory MCP.",
        "metadata": {"repo_remote": repo_remote},
    }
    return _table_upsert(client, "workspaces", payload)


def _resolve_or_create_project(
    client: Any,
    project_id: str | None = None,
    owner_id: str | None = None,
    repo_path: str | None = None,
    repo_url: str | None = None,
    project_name: str | None = None,
    project_slug: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    create_if_missing: bool = True,
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Resuelve o crea automaticamente un proyecto y su workspace."""
    resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
    repo_ctx = detect_repo_context(repo_path).to_dict()
    if repo_url:
        repo_ctx["repo_remote"] = repo_url
    workspace = _ensure_workspace(
        client,
        resolved_owner,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        repo_remote=repo_ctx.get("repo_remote", ""),
    )

    if project_id:
        validated = validate_project_id(project_id)
        rows = _table_select(client, "projects", {"id": validated})
        if rows:
            project = rows[0]
            repo_update = {
                "id": project["id"],
                "owner_id": resolved_owner,
                "workspace_id": workspace.get("id"),
                "repo_path": repo_ctx["repo_root"],
                "repo_remote": repo_ctx["repo_remote"],
                "repo_branch": repo_ctx["repo_branch"],
                "repo_last_commit": repo_ctx["repo_commit"],
                "repo_status": {"changed_files": repo_ctx["repo_status"]},
                "metadata": {
                    **(project.get("metadata") or {}),
                    "repo_provider": repo_ctx.get("repo_provider", "local"),
                },
            }
            return _table_upsert(client, "projects", repo_update), workspace, repo_ctx

    slug = project_slug or repo_ctx.get("repo_slug") or slugify(project_name or "memory-project")
    rows = _table_select(client, "projects", {"owner_id": resolved_owner, "slug": slug})
    if rows:
        project = rows[0]
        payload = {
            "id": project["id"],
            "owner_id": resolved_owner,
            "workspace_id": workspace.get("id"),
            "name": project_name or project.get("name") or repo_ctx.get("repo_name"),
            "slug": slug,
            "description": description or project.get("description", ""),
            "primary_interface": detect_interface(),
            "repo_path": repo_ctx["repo_root"],
            "repo_remote": repo_ctx["repo_remote"],
            "repo_branch": repo_ctx["repo_branch"],
            "repo_last_commit": repo_ctx["repo_commit"],
            "repo_status": {"changed_files": repo_ctx["repo_status"]},
            "project_summary": project.get("project_summary", ""),
            "metadata": {
                **(project.get("metadata") or {}),
                "repo_provider": repo_ctx.get("repo_provider", "local"),
            },
        }
        return _table_upsert(client, "projects", payload), workspace, repo_ctx

    if not create_if_missing:
        raise ValueError("Project could not be resolved automatically")

    payload = {
        "owner_id": resolved_owner,
        "workspace_id": workspace.get("id"),
        "name": project_name or repo_ctx.get("repo_name") or "Memory Project",
        "slug": slug,
        "description": description or "Auto-created by Memory MCP from repo context.",
        "primary_interface": detect_interface(),
        "repo_path": repo_ctx["repo_root"],
        "repo_remote": repo_ctx["repo_remote"],
        "repo_branch": repo_ctx["repo_branch"],
        "repo_last_commit": repo_ctx["repo_commit"],
        "repo_status": {"changed_files": repo_ctx["repo_status"]},
        "project_summary": "",
        "metadata": {"repo_provider": repo_ctx.get("repo_provider", "local")},
    }
    project = _table_upsert(client, "projects", payload)
    _record_timeline(
        client,
        project["id"],
        resolved_owner,
        "project.auto_created",
        f"Created project '{project['name']}' from repository context.",
        {"interface": detect_interface(), "repo": repo_ctx},
    )
    return project, workspace, repo_ctx


def _find_active_session(client: Any, project_id: str) -> dict[str, Any] | None:
    """Retorna la sesion activa mas reciente si existe."""
    sessions = _sort_rows(_table_select(client, "sessions", {"project_id": project_id}))
    for session in sessions:
        if session.get("status") == "active":
            return session
    return None


def _search_rows(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    """Hace una busqueda lexical simple cuando no hay embeddings."""
    tokens = [token for token in _normalize_text(query).split() if token]
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        haystack = _normalize_text(
            " ".join(
                [
                    str(row.get("title", "")),
                    str(row.get("summary", "")),
                    str(row.get("content", "")),
                    str(row.get("details", "")),
                ]
            )
        )
        score = sum(3 if token in haystack else 0 for token in tokens)
        if score:
            enriched = dict(row)
            enriched["score"] = score
            scored.append((score, enriched))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def _upsert_warning(
    client: Any,
    project_id: str,
    owner_id: str,
    message: str,
    severity: str,
    interface: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Guarda una advertencia y registra timeline."""
    warning = _table_upsert(
        client,
        "warnings",
        {
            "project_id": project_id,
            "owner_id": owner_id,
            "message": message,
            "severity": validate_severity(severity),
            "interface": interface,
            "is_active": True,
            "metadata": _safe_json(metadata or {}),
        },
    )
    _record_timeline(
        client,
        project_id,
        owner_id,
        "warning.added",
        message,
        {"interface": interface, "severity": severity, "warning_id": warning.get("id")},
    )
    return warning


def _detect_conflicts(
    client: Any,
    project_id: str,
    owner_id: str,
    artifact_type: str,
    text: str,
    title: str = "",
    dependencies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Genera advertencias heuristicas para duplicados o contradicciones."""
    interface_name = detect_interface()
    generated: list[dict[str, Any]] = []
    normalized_text = _normalize_text(text)
    normalized_title = _normalize_text(title)

    if artifact_type == "decision":
        decisions = _table_select(client, "decisions", {"project_id": project_id})
        contradiction_pairs = [
            ("use", "do not use"),
            ("enable", "disable"),
            ("allow", "deny"),
        ]
        for decision in decisions:
            existing = _normalize_text(decision.get("summary", ""))
            if existing and existing == normalized_text:
                generated.append(
                    _upsert_warning(
                        client,
                        project_id,
                        owner_id,
                        f"Potential duplicate decision detected: '{text}'.",
                        "low",
                        interface_name,
                        {"conflict_type": "duplicate_decision"},
                    )
                )
                break
            for positive, negative in contradiction_pairs:
                if positive in existing and negative in normalized_text:
                    generated.append(
                        _upsert_warning(
                            client,
                            project_id,
                            owner_id,
                            (
                                "Possible contradictory decision detected between existing memory "
                                f"and '{text}'."
                            ),
                            "medium",
                            interface_name,
                            {"conflict_type": "decision_contradiction"},
                        )
                    )
                    return generated

    if artifact_type == "task" and normalized_title:
        tasks = _table_select(client, "tasks", {"project_id": project_id})
        for task in tasks:
            if _normalize_text(task.get("title", "")) == normalized_title:
                generated.append(
                    _upsert_warning(
                        client,
                        project_id,
                        owner_id,
                        f"Potential duplicate task detected: '{title}'.",
                        "low",
                        interface_name,
                        {"conflict_type": "duplicate_task"},
                    )
                )
                break

    if artifact_type == "file_memory":
        known_files = {
            row.get("file_path", "") for row in _table_select(client, "file_memory", {"project_id": project_id})
        }
        for dependency in dependencies or []:
            if dependency and dependency not in known_files:
                generated.append(
                    _upsert_warning(
                        client,
                        project_id,
                        owner_id,
                        f"Dependency '{dependency}' is referenced but not documented in file memory.",
                        "medium",
                        interface_name,
                        {"conflict_type": "missing_file_dependency"},
                    )
                )
    return generated


def _build_session_summary(state: dict[str, Any], completed_work: str = "") -> dict[str, str]:
    """Construye un resumen de sesion desde el estado sincronizado."""
    summary = completed_work or state.get("summary") or state.get("current_goal") or "Session ended."
    remaining = state.get("remaining_work") or state.get("pending_items") or ""
    next_step = state.get("next_step") or state.get("recommended_next_step") or ""
    return {
        "summary": str(summary).strip(),
        "remaining_work": str(remaining).strip(),
        "next_step": str(next_step).strip(),
    }


def _collect_bundle(client: Any, project_id: str) -> dict[str, Any]:
    """Reune todas las entidades relevantes del proyecto."""
    project_rows = _table_select(client, "projects", {"id": project_id})
    project = project_rows[0] if project_rows else {}
    workspace_rows = _table_select(client, "workspaces", {"id": project.get("workspace_id")})
    return {
        "project": project,
        "workspace": workspace_rows[0] if workspace_rows else {},
        "decisions": _sort_rows(_table_select(client, "decisions", {"project_id": project_id})),
        "tasks": _sort_rows(_table_select(client, "tasks", {"project_id": project_id})),
        "preferences": _sort_rows(_table_select(client, "preferences", {"project_id": project_id})),
        "warnings": _sort_rows(_table_select(client, "warnings", {"project_id": project_id})),
        "sessions": _sort_rows(_table_select(client, "sessions", {"project_id": project_id})),
        "checkpoints": _sort_rows(_table_select(client, "checkpoints", {"project_id": project_id})),
        "file_memory": _sort_rows(_table_select(client, "file_memory", {"project_id": project_id})),
        "file_relations": _sort_rows(
            _table_select(client, "file_relations", {"project_id": project_id}),
            key="source_file",
            reverse=False,
        ),
        "prompt_patterns": _sort_rows(
            _table_select(client, "prompt_patterns", {"project_id": project_id})
        ),
        "timeline": _sort_rows(_table_select(client, "timeline_events", {"project_id": project_id})),
        "memory_documents": _sort_rows(
            _table_select(client, "memory_documents", {"project_id": project_id})
        ),
        "retention_policy": _table_select(client, "retention_policies", {"project_id": project_id}),
    }


def _markdown_bundle(bundle: dict[str, Any]) -> str:
    """Convierte un bundle a Markdown portable."""
    project = bundle.get("project") or {}
    lines = [f"# {project.get('name', 'Memory MCP Export')}", ""]
    lines.append(f"- Slug: `{project.get('slug', '')}`")
    lines.append(f"- Repo: `{project.get('repo_remote', '') or project.get('repo_path', '')}`")
    lines.append("")
    lines.append("## Resume")
    lines.append(project.get("project_summary", "No summary recorded."))
    lines.append("")
    for section_name in ("decisions", "tasks", "warnings", "checkpoints", "file_memory"):
        rows = bundle.get(section_name) or []
        lines.append(f"## {section_name.replace('_', ' ').title()}")
        if not rows:
            lines.append("- No entries")
        for row in rows:
            title = row.get("title") or row.get("summary") or row.get("message") or row.get("file_path")
            lines.append(f"- {title}")
        lines.append("")
    return "\n".join(lines).strip()


def _project_result(project: dict[str, Any], workspace: dict[str, Any], repo: dict[str, Any]) -> dict[str, Any]:
    """Normaliza la respuesta de resolucion de proyecto."""
    return {
        "status": "ok",
        "project_id": project.get("id"),
        "project_slug": project.get("slug"),
        "project_name": project.get("name"),
        "workspace_id": workspace.get("id"),
        "workspace_slug": workspace.get("slug"),
        "repo_root": repo.get("repo_root"),
        "repo_remote": repo.get("repo_remote"),
        "repo_branch": repo.get("repo_branch"),
    }


@server.tool(name="resolve_project", description="Resuelve o crea un proyecto automaticamente.")
def resolve_project(
    project_id: str | None = None,
    owner_id: str | None = None,
    repo_path: str | None = None,
    repo_url: str | None = None,
    project_name: str | None = None,
    project_slug: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    """Resuelve o crea automaticamente un proyecto usando el repo actual."""
    client = _client(owner_id)
    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            repo_url=repo_url,
            project_name=project_name,
            project_slug=project_slug,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            create_if_missing=create_if_missing,
        )
        return _project_result(project, workspace, repo)
    except Exception as exc:
        return {"error": str(exc), "tool": "resolve_project"}


@server.tool(name="create_project", description="Crea un proyecto con metadata de repo y workspace.")
def create_project(
    name: str | None = None,
    slug: str | None = None,
    description: str = "",
    owner_id: str | None = None,
    repo_path: str | None = None,
    repo_url: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    """Crea explicitamente un proyecto o reusa uno existente."""
    client = _client(owner_id)
    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            owner_id=owner_id,
            repo_path=repo_path,
            repo_url=repo_url,
            project_name=name,
            project_slug=slug,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            create_if_missing=True,
            description=description,
        )
        return _project_result(project, workspace, repo)
    except Exception as exc:
        return {"error": str(exc), "tool": "create_project"}


@server.tool(name="list_projects", description="Lista proyectos del owner o workspace actual.")
def list_projects(
    owner_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Lista proyectos disponibles para el owner actual."""
    client = _client(owner_id)
    try:
        resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
        filters: dict[str, Any] = {"owner_id": resolved_owner}
        if workspace_id:
            filters["workspace_id"] = workspace_id
        projects = _sort_rows(_table_select(client, "projects", filters), key="name", reverse=False)
        return {"status": "ok", "projects": projects, "count": len(projects)}
    except Exception as exc:
        return {"error": str(exc), "tool": "list_projects"}


@server.tool(name="load_unified_context", description="Carga contexto persistente optimizado.")
def load_unified_context(
    project_id: str | None = None,
    interface: str | None = None,
    owner_id: str | None = None,
    repo_path: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Carga el contexto consolidado del proyecto y lo optimiza por interfaz."""
    target_interface = interface or detect_interface()
    client = _client(owner_id)

    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            workspace_id=workspace_id,
            create_if_missing=True,
        )
        bundle = _collect_bundle(client, project["id"])
        bundle["workspace"] = workspace
        bundle["metadata"] = {
            "interface": target_interface,
            "recommended_model": get_model_for_interface(target_interface),
            "repo": repo,
            "retention_policy": (bundle.get("retention_policy") or [{}])[0],
        }
        formatted = format_context(bundle)
        optimized = optimizer.optimize_for_interface(formatted, target_interface)
        estimated_tokens = optimizer.estimate_tokens(optimized)
        return router.optimize_context_for_model(
            optimized["metadata"]["recommended_model"],
            optimized,
            estimated_tokens,
        )
    except Exception as exc:
        return {"error": str(exc), "tool": "load_unified_context"}


@server.tool(
    name="save_cross_interface_decision",
    description="Guarda decisiones compartidas entre interfaces.",
)
def save_cross_interface_decision(
    project_id: str | None = None,
    summary: str = "",
    details: str = "",
    interface: str | None = None,
    decision_type: str = "general",
    owner_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    repo_path: str | None = None,
    file_paths: list[str] | None = None,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Persiste una decision reusable por varias interfaces."""
    client = _client(owner_id)
    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            create_if_missing=True,
        )
        payload = format_decision(
            {
                "project_id": project["id"],
                "interface": interface or detect_interface(),
                "summary": summary,
                "details": details,
                "decision_type": decision_type,
                "metadata": {
                    **(metadata or {}),
                    "file_paths": file_paths or [],
                    "repo": repo,
                },
                "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            }
        )
        payload["owner_id"] = owner_id or os.getenv("OWNER_ID", "default-owner")
        decision = _table_upsert(client, "decisions", payload)
        semantic_doc = _upsert_memory_document(
            client,
            project["id"],
            payload["owner_id"],
            "decision",
            str(decision.get("id")),
            summary,
            f"{summary}\n\n{details}",
            keywords=[decision_type, *(file_paths or [])],
            metadata=payload["metadata"],
            embedding=embedding,
        )
        warnings = _detect_conflicts(
            client,
            project["id"],
            payload["owner_id"],
            "decision",
            summary,
        )
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "decision.saved",
            summary,
            {
                "interface": payload["interface"],
                "decision_id": decision.get("id"),
                "semantic_document_id": semantic_doc.get("id"),
            },
        )
        return {
            "status": "ok",
            "project_id": project.get("id"),
            "decision_id": decision.get("id"),
            "decision_summary": decision.get("summary"),
            "warning_count": len(warnings),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "save_cross_interface_decision"}


@server.tool(name="update_task_status", description="Crea o actualiza tareas del proyecto.")
def update_task_status(
    task_id: str | None = None,
    project_id: str | None = None,
    status: str = "pending",
    owner_id: str | None = None,
    title: str | None = None,
    priority: str = "medium",
    details: str = "",
    repo_path: str | None = None,
) -> dict[str, Any]:
    """Actualiza el estado de una tarea y detecta duplicados."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            create_if_missing=True,
        )
        normalized_title = title or (task_id.replace("-", " ").title() if task_id else "Untitled task")
        payload = {
            "id": task_id,
            "project_id": project["id"],
            "title": normalized_title,
            "status": status.strip().lower(),
            "priority": priority,
            "details": details,
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
        }
        task = _table_upsert(client, "tasks", payload)
        warnings = _detect_conflicts(
            client,
            project["id"],
            payload["owner_id"],
            "task",
            details or normalized_title,
            title=normalized_title,
        )
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "task.updated",
            f"{normalized_title} -> {payload['status']}",
            {"task_id": task.get("id"), "interface": detect_interface()},
        )
        return {
            "status": "ok",
            "task_id": task.get("id"),
            "task_title": task.get("title"),
            "task_status": task.get("status"),
            "warning_count": len(warnings),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "update_task_status"}


@server.tool(name="create_session", description="Crea una sesion y guarda contexto git.")
def create_session(
    project_id: str | None = None,
    interface: str | None = None,
    model_name: str | None = None,
    owner_id: str | None = None,
    repo_path: str | None = None,
    current_goal: str = "",
) -> dict[str, Any]:
    """Crea una sesion activa y captura contexto git del repo."""
    client = _client(owner_id)
    try:
        project, _, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            create_if_missing=True,
        )
        active = _find_active_session(client, project["id"])
        interface_name = interface or detect_interface()
        if active and active.get("interface") != interface_name:
            _record_timeline(
                client,
                project["id"],
                owner_id or os.getenv("OWNER_ID", "default-owner"),
                "session.handoff",
                f"Handoff from {active.get('interface')} to {interface_name}.",
                {"from": active.get("interface"), "to": interface_name},
            )
        model = model_name or router.recommend_model("coding")
        payload = {
            "project_id": project["id"],
            "interface": interface_name,
            "model_name": model,
            "status": "active",
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            "metadata": {"repo": repo, "current_goal": current_goal},
        }
        session = _table_upsert(client, "sessions", payload)
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "session.created",
            f"Started {interface_name} session.",
            {"session_id": session.get("id"), "interface": interface_name, "repo": repo},
        )
        return {
            "status": "ok",
            "project_id": project.get("id"),
            "session_id": session.get("id"),
            "interface": session.get("interface"),
            "model_name": session.get("model_name"),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "create_session"}


@server.tool(name="end_session", description="Finaliza una sesion y genera resumen automatico.")
def end_session(
    session_id: str | None = None,
    project_id: str | None = None,
    owner_id: str | None = None,
    completed_work: str = "",
    remaining_work: str = "",
    next_step: str = "",
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Marca una sesion como finalizada y guarda un checkpoint resumen."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        session = None
        if session_id:
            rows = _table_select(client, "sessions", {"id": session_id})
            session = rows[0] if rows else None
        if session is None:
            session = _find_active_session(client, project["id"])
        if session is None:
            raise ValueError("No active session available to end")
        state_rows = _table_select(client, "session_state", {"session_id": session.get("id")})
        state = state_rows[0].get("state", {}) if state_rows else {}
        summary_bits = _build_session_summary(state, completed_work=completed_work)
        if remaining_work:
            summary_bits["remaining_work"] = remaining_work
        if next_step:
            summary_bits["next_step"] = next_step
        ended = _table_upsert(
            client,
            "sessions",
            {
                "id": session.get("id"),
                "project_id": project["id"],
                "status": "ended",
                "ended_at": _now_iso(),
                "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                "metadata": {
                    **(session.get("metadata") or {}),
                    "summary": summary_bits,
                    "blockers": blockers or [],
                },
            },
        )
        checkpoint = save_checkpoint(
            project_id=project["id"],
            owner_id=owner_id,
            title=f"Session summary: {session.get('interface', 'unknown')}",
            architecture_summary=state.get("architecture_summary", ""),
            functional_state=summary_bits["summary"],
            blockers=blockers or [],
            next_steps=[summary_bits["next_step"]] if summary_bits["next_step"] else [],
            tags=["session-summary", session.get("interface", "unknown")],
        )
        _record_timeline(
            client,
            project["id"],
            owner_id or os.getenv("OWNER_ID", "default-owner"),
            "session.ended",
            summary_bits["summary"],
            {"session_id": ended.get("id"), "next_step": summary_bits["next_step"]},
        )
        checkpoint_data = checkpoint.get("checkpoint") if checkpoint else None
        return {
            "status": "ok",
            "session_id": ended.get("id"),
            "session_status": ended.get("status"),
            "checkpoint_id": checkpoint_data.get("id") if checkpoint_data else None,
            "next_step": summary_bits.get("next_step", ""),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "end_session"}


@server.tool(name="add_warning", description="Registra advertencias inteligentes.")
def add_warning(
    project_id: str | None = None,
    message: str = "",
    severity: str = "medium",
    owner_id: str | None = None,
    interface: str | None = None,
) -> dict[str, Any]:
    """Registra una advertencia activa en la memoria persistente."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        warning = _upsert_warning(
            client,
            project["id"],
            owner_id or os.getenv("OWNER_ID", "default-owner"),
            message.strip(),
            severity,
            interface or detect_interface(),
        )
        return {
            "status": "ok",
            "warning_id": warning.get("id"),
            "severity": warning.get("severity"),
            "message": warning.get("message"),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "add_warning"}


@server.tool(name="get_active_warnings", description="Lista advertencias activas.")
def get_active_warnings(
    project_id: str | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Obtiene todas las advertencias activas de un proyecto."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        warnings = _sort_rows(
            _table_select(client, "warnings", {"project_id": project["id"], "is_active": True})
        )
        return {
            "status": "ok",
            "project_id": project.get("id"),
            "warnings": warnings,
            "count": len(warnings),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "get_active_warnings"}


@server.tool(name="sync_session_state", description="Sincroniza el estado de sesion.")
def sync_session_state(
    session_id: str | None = None,
    project_id: str | None = None,
    state: dict[str, Any] | None = None,
    owner_id: str | None = None,
    summary: str = "",
) -> dict[str, Any]:
    """Sincroniza el estado de una sesion entre interfaces."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        active = None
        if session_id:
            rows = _table_select(client, "sessions", {"id": session_id})
            active = rows[0] if rows else None
        if active is None:
            active = _find_active_session(client, project["id"])
        if active is None:
            session_result = create_session(project_id=project["id"], owner_id=owner_id)
            active = session_result.get("session")
        if active is None:
            raise ValueError("Session could not be resolved or created")
        payload = {
            "session_id": active.get("id"),
            "project_id": project["id"],
            "state": _safe_json(state or {}),
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            "metadata": {"summary": summary},
        }
        session_state = _table_upsert(client, "session_state", payload)
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "session.synced",
            summary or "Synced working session state.",
            {"session_id": active.get("id"), "interface": active.get("interface")},
        )
        return {
            "status": "ok",
            "session_id": active.get("id"),
            "interface": active.get("interface"),
            "state_keys": sorted(list((session_state.get("state") or {}).keys())),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "sync_session_state"}


@server.tool(name="get_interface_analytics", description="Resume uso por interfaz.")
def get_interface_analytics(
    project_id: str | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Lee analitica agregada por interfaz desde la vista SQL."""
    client = _client(owner_id)
    try:
        project = None
        if project_id:
            project, _, _ = _resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=True,
            )
        filters: dict[str, Any] = {}
        if project:
            filters["project_id"] = project["id"]
        analytics = _table_select(client, "interface_analytics", filters)
        return {"status": "ok", "analytics": analytics, "interfaces": len(analytics)}
    except Exception as exc:
        return {"error": str(exc), "tool": "get_interface_analytics"}


@server.tool(name="save_file_memory", description="Guarda memoria por archivo y relaciones.")
def save_file_memory(
    file_path: str,
    summary: str,
    project_id: str | None = None,
    owner_id: str | None = None,
    dependencies: list[str] | None = None,
    symbols: list[str] | None = None,
    file_role: str = "module",
    importance: str = "medium",
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Guarda memoria estructurada por archivo y relaciones."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        normalized_dependencies = [str(item).strip() for item in dependencies or [] if str(item).strip()]
        payload = {
            "project_id": project["id"],
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            "file_path": file_path,
            "file_role": file_role,
            "summary": summary,
            "symbols": symbols or [],
            "importance": importance,
            "metadata": {"dependencies": normalized_dependencies},
        }
        file_entry = _table_upsert(client, "file_memory", payload)
        for dependency in normalized_dependencies:
            _table_upsert(
                client,
                "file_relations",
                {
                    "project_id": project["id"],
                    "owner_id": payload["owner_id"],
                    "source_file": file_path,
                    "target_file": dependency,
                    "relation_type": "depends_on",
                },
            )
        _upsert_memory_document(
            client,
            project["id"],
            payload["owner_id"],
            "file_memory",
            file_path,
            file_path,
            summary,
            keywords=[file_role, importance, *normalized_dependencies],
            metadata={"symbols": symbols or []},
            embedding=embedding,
        )
        warnings = _detect_conflicts(
            client,
            project["id"],
            payload["owner_id"],
            "file_memory",
            summary,
            dependencies=normalized_dependencies,
        )
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "file_memory.saved",
            f"Documented {file_path}.",
            {"dependencies": normalized_dependencies, "symbols": symbols or []},
        )
        return {"status": "ok", "file_memory": file_entry, "warnings": warnings}
    except Exception as exc:
        return {"error": str(exc), "tool": "save_file_memory"}


@server.tool(name="save_checkpoint", description="Guarda checkpoints de arquitectura y estado.")
def save_checkpoint(
    title: str,
    functional_state: str,
    project_id: str | None = None,
    owner_id: str | None = None,
    architecture_summary: str = "",
    blockers: list[str] | None = None,
    next_steps: list[str] | None = None,
    tags: list[str] | None = None,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Guarda checkpoints con estado funcional, blockers y siguientes pasos."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        payload = {
            "project_id": project["id"],
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            "title": title,
            "architecture_summary": architecture_summary,
            "functional_state": functional_state,
            "blockers": blockers or [],
            "next_steps": next_steps or [],
            "tags": tags or [],
            "metadata": {"interface": detect_interface()},
        }
        checkpoint = _table_upsert(client, "checkpoints", payload)
        _upsert_memory_document(
            client,
            project["id"],
            payload["owner_id"],
            "checkpoint",
            str(checkpoint.get("id")),
            title,
            "\n\n".join([title, architecture_summary, functional_state]),
            keywords=[*(tags or []), *(next_steps or [])],
            metadata={"blockers": blockers or [], "next_steps": next_steps or []},
            embedding=embedding,
        )
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "checkpoint.saved",
            title,
            {"checkpoint_id": checkpoint.get("id"), "tags": tags or []},
        )
        return {"status": "ok", "checkpoint": checkpoint}
    except Exception as exc:
        return {"error": str(exc), "tool": "save_checkpoint"}


@server.tool(name="save_prompt_pattern", description="Guarda prompts utiles y patrones de respuesta.")
def save_prompt_pattern(
    title: str,
    prompt: str,
    project_id: str | None = None,
    owner_id: str | None = None,
    category: str = "general",
    usage_notes: str = "",
    response_style: str = "",
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Guarda prompts efectivos para reutilizarlos luego."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        payload = {
            "project_id": project["id"],
            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
            "title": title,
            "category": category,
            "prompt": prompt,
            "usage_notes": usage_notes,
            "response_style": response_style,
            "metadata": {"interface": detect_interface()},
        }
        pattern = _table_upsert(client, "prompt_patterns", payload)
        _upsert_memory_document(
            client,
            project["id"],
            payload["owner_id"],
            "prompt_pattern",
            str(pattern.get("id")),
            title,
            f"{prompt}\n\n{usage_notes}\n\n{response_style}",
            keywords=[category],
            metadata={"response_style": response_style},
            embedding=embedding,
        )
        _record_timeline(
            client,
            project["id"],
            payload["owner_id"],
            "prompt.saved",
            title,
            {"category": category},
        )
        return {"status": "ok", "prompt_pattern": pattern}
    except Exception as exc:
        return {"error": str(exc), "tool": "save_prompt_pattern"}


@server.tool(
    name="capture_project_memory",
    description="Guarda automaticamente decisiones, tareas, checkpoints, archivos y estado en una sola llamada.",
)
def capture_project_memory(
    project_id: str | None = None,
    owner_id: str | None = None,
    summary: str = "",
    what_was_done: str = "",
    what_is_left: list[str] | None = None,
    next_step: str = "",
    decisions: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    blockers: list[str] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    file_memory: list[dict[str, Any]] | None = None,
    prompt_patterns: list[dict[str, Any]] | None = None,
    session_state: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    repo_path: str | None = None,
    auto_checkpoint: bool = True,
    auto_sync_session: bool = True,
) -> dict[str, Any]:
    """Guarda de forma orquestada todo el contexto importante de una iteracion.

    Esta tool sirve para prompts tipo "guarda todo en tu memoria". El modelo puede
    mandar en una sola llamada decisiones, tareas, warnings, archivos, prompts y estado.
    """
    client = _client(owner_id)
    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            repo_path=repo_path,
            create_if_missing=True,
        )
        resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
        saved: dict[str, list[Any]] = {
            "decisions": [],
            "tasks": [],
            "warnings": [],
            "file_memory": [],
            "prompt_patterns": [],
        }

        for decision in decisions or []:
            result = save_cross_interface_decision(
                project_id=project["id"],
                owner_id=resolved_owner,
                summary=str(decision.get("summary", "")).strip(),
                details=str(decision.get("details", "")).strip(),
                decision_type=str(decision.get("decision_type", "general")),
                metadata=decision.get("metadata") or {},
                file_paths=_ensure_list(decision.get("file_paths")),
                repo_path=repo_path,
            )
            if result.get("decision"):
                saved["decisions"].append(result["decision"])

        for task in tasks or []:
            result = update_task_status(
                task_id=task.get("id"),
                project_id=project["id"],
                owner_id=resolved_owner,
                title=task.get("title"),
                status=str(task.get("status", "pending")),
                priority=str(task.get("priority", "medium")),
                details=str(task.get("details", "")),
                repo_path=repo_path,
            )
            if result.get("status") == "ok":
                saved["tasks"].append(
                    {
                        "task_id": result.get("task_id"),
                        "task_title": result.get("task_title"),
                        "task_status": result.get("task_status"),
                    }
                )
            warning_count = int(result.get("warning_count", 0) or 0)
            if warning_count:
                saved["warnings"].extend([{"source": "task", "count": warning_count}])

        for warning in warnings or []:
            result = add_warning(
                project_id=project["id"],
                owner_id=resolved_owner,
                message=str(warning.get("message", "")).strip(),
                severity=str(warning.get("severity", "medium")),
                interface=warning.get("interface"),
            )
            if result.get("warning"):
                saved["warnings"].append(result["warning"])

        for file_item in file_memory or []:
            result = save_file_memory(
                project_id=project["id"],
                owner_id=resolved_owner,
                file_path=str(file_item.get("file_path", "")).strip(),
                summary=str(file_item.get("summary", "")).strip(),
                dependencies=_ensure_list(file_item.get("dependencies")),
                symbols=_ensure_list(file_item.get("symbols")),
                file_role=str(file_item.get("file_role", "module")),
                importance=str(file_item.get("importance", "medium")),
            )
            if result.get("file_memory"):
                saved["file_memory"].append(result["file_memory"])
            warning_count = int(result.get("warning_count", 0) or 0)
            if warning_count:
                saved["warnings"].extend([{"source": "file_memory", "count": warning_count}])

        for pattern in prompt_patterns or []:
            result = save_prompt_pattern(
                project_id=project["id"],
                owner_id=resolved_owner,
                title=str(pattern.get("title", "")).strip(),
                prompt=str(pattern.get("prompt", "")).strip(),
                category=str(pattern.get("category", "general")),
                usage_notes=str(pattern.get("usage_notes", "")),
                response_style=str(pattern.get("response_style", "")),
            )
            if result.get("prompt_pattern"):
                saved["prompt_patterns"].append(result["prompt_pattern"])

        synced_state = None
        combined_state = dict(session_state or {})
        if summary:
            combined_state.setdefault("summary", summary)
        if what_was_done:
            combined_state.setdefault("what_was_done", what_was_done)
        if next_step:
            combined_state.setdefault("next_step", next_step)
        if what_is_left:
            combined_state.setdefault("remaining_work", what_is_left)

        if auto_sync_session and combined_state:
            sync_result = sync_session_state(
                project_id=project["id"],
                owner_id=resolved_owner,
                state=combined_state,
                summary=summary or what_was_done,
            )
            synced_state = sync_result.get("session_state")

        checkpoint = None
        if auto_checkpoint and (summary or what_was_done or blockers or next_step or what_is_left):
            checkpoint_result = save_checkpoint(
                project_id=project["id"],
                owner_id=resolved_owner,
                title=summary or "Auto memory checkpoint",
                architecture_summary=str(combined_state.get("architecture_summary", "")),
                functional_state=what_was_done or summary,
                blockers=blockers or [],
                next_steps=[*(_ensure_list(what_is_left)[:3]), next_step] if next_step else _ensure_list(what_is_left),
                tags=tags or ["auto-memory"],
            )
            checkpoint = checkpoint_result.get("checkpoint")

        _record_timeline(
            client,
            project["id"],
            resolved_owner,
            "memory.capture",
            summary or what_was_done or "Captured project memory package.",
            {
                "repo": repo,
                "saved_counts": {key: len(value) for key, value in saved.items()},
                "checkpoint": bool(checkpoint),
                "synced_state": bool(synced_state),
            },
        )
        return {
            "status": "ok",
            "project": project,
            "workspace": workspace,
            "repo": repo,
            "saved": {key: len(value) for key, value in saved.items()},
            "checkpoint": checkpoint,
            "session_state": synced_state,
            "next_step": next_step or (what_is_left[0] if what_is_left else ""),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "capture_project_memory"}


@server.tool(name="search_semantic_memory", description="Busca memoria por significado o texto.")
def search_semantic_memory(
    query: str,
    project_id: str | None = None,
    owner_id: str | None = None,
    query_embedding: list[float] | None = None,
    limit: int = 5,
    source_types: list[str] | None = None,
) -> dict[str, Any]:
    """Busca contexto relevante usando embeddings o fallback lexical."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        semantic_matches: list[dict[str, Any]] = []
        if query_embedding:
            semantic_matches = _table_rpc(
                client,
                "match_memory_documents",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter_project_id": project["id"],
                    "filter_owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                },
            ) or []
        if not semantic_matches:
            rows = _table_select(client, "memory_documents", {"project_id": project["id"]})
            if source_types:
                rows = [row for row in rows if row.get("source_type") in set(source_types)]
            semantic_matches = _search_rows(rows, query, limit)
        return {
            "status": "ok",
            "query": query,
            "matches": semantic_matches[:limit],
            "match_count": min(limit, len(semantic_matches)),
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "search_semantic_memory"}


@server.tool(name="get_project_timeline", description="Devuelve la linea de tiempo del proyecto.")
def get_project_timeline(
    project_id: str | None = None,
    owner_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Obtiene la evolucion reciente del proyecto."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        timeline = _sort_rows(_table_select(client, "timeline_events", {"project_id": project["id"]}))
        return {"status": "ok", "timeline": timeline[:limit], "count": len(timeline)}
    except Exception as exc:
        return {"error": str(exc), "tool": "get_project_timeline"}


@server.tool(name="export_memory_bundle", description="Exporta memoria a JSON o Markdown.")
def export_memory_bundle(
    project_id: str | None = None,
    owner_id: str | None = None,
    format: str = "json",
) -> dict[str, Any]:
    """Exporta la memoria del proyecto a JSON o Markdown."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        bundle = _collect_bundle(client, project["id"])
        if format.strip().lower() == "markdown":
            return {"status": "ok", "format": "markdown", "content": _markdown_bundle(bundle)}
        return {"status": "ok", "format": "json", "content": json.dumps(bundle, indent=2)}
    except Exception as exc:
        return {"error": str(exc), "tool": "export_memory_bundle"}


@server.tool(name="import_memory_bundle", description="Importa memoria desde JSON o diccionario.")
def import_memory_bundle(
    payload: dict[str, Any] | str,
    owner_id: str | None = None,
    project_id: str | None = None,
    merge: bool = True,
) -> dict[str, Any]:
    """Importa un bundle exportado anteriormente."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        parsed = json.loads(payload) if isinstance(payload, str) else payload
        collections = [
            "decisions",
            "tasks",
            "preferences",
            "warnings",
            "sessions",
            "checkpoints",
            "file_memory",
            "prompt_patterns",
        ]
        imported: dict[str, int] = {}
        for collection in collections:
            imported[collection] = 0
            for row in parsed.get(collection, []):
                candidate = dict(row)
                candidate["project_id"] = project["id"]
                candidate["owner_id"] = owner_id or os.getenv("OWNER_ID", "default-owner")
                if not merge:
                    candidate.pop("id", None)
                _table_upsert(client, collection, candidate)
                imported[collection] += 1
        _record_timeline(
            client,
            project["id"],
            owner_id or os.getenv("OWNER_ID", "default-owner"),
            "bundle.imported",
            "Imported memory bundle into project.",
            imported,
        )
        return {"status": "ok", "imported": imported, "project": project}
    except Exception as exc:
        return {"error": str(exc), "tool": "import_memory_bundle"}


@server.tool(name="resume_project", description="Devuelve un resumen listo para retomar el proyecto.")
def resume_project(
    project_id: str | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Devuelve el resumen de continuidad del proyecto."""
    client = _client(owner_id)
    try:
        project, workspace, repo = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        bundle = _collect_bundle(client, project["id"])
        tasks = [task for task in bundle.get("tasks", []) if task.get("status") != "completed"]
        warnings = [warning for warning in bundle.get("warnings", []) if warning.get("is_active")]
        checkpoints = bundle.get("checkpoints", [])
        latest_checkpoint = checkpoints[0] if checkpoints else {}
        latest_state_rows = _sort_rows(
            _table_select(client, "session_state", {"project_id": project["id"]})
        )
        latest_state = latest_state_rows[0].get("state", {}) if latest_state_rows else {}
        recent_decisions = bundle.get("decisions", [])[:3]
        next_step = (
            latest_state.get("next_step")
            or (latest_checkpoint.get("next_steps") or [""])[0]
            or (tasks[0].get("title") if tasks else "Review latest checkpoint and continue implementation.")
        )
        summary = {
            "project_id": project["id"],
            "project_name": project.get("name"),
            "workspace": workspace,
            "repo": repo,
            "what_was_done": latest_checkpoint.get("functional_state")
            or latest_state.get("summary")
            or project.get("project_summary")
            or "Project memory loaded.",
            "what_is_left": [task.get("title") for task in tasks[:5]],
            "warnings": [warning.get("message") for warning in warnings[:5]],
            "recent_decisions": [decision.get("summary") for decision in recent_decisions],
            "next_step": next_step,
        }
        _record_timeline(
            client,
            project["id"],
            owner_id or os.getenv("OWNER_ID", "default-owner"),
            "project.resumed",
            summary["what_was_done"],
            {"next_step": next_step},
        )
        return {"status": "ok", "resume": summary}
    except Exception as exc:
        return {"error": str(exc), "tool": "resume_project"}


@server.tool(name="apply_retention_policy", description="Aplica politicas de retencion y archivo.")
def apply_retention_policy(
    project_id: str | None = None,
    owner_id: str | None = None,
    keep_recent_sessions: int = 5,
    keep_recent_decisions: int = 20,
    archive_after_days: int = 30,
    summarize_archived: bool = True,
) -> dict[str, Any]:
    """Guarda una politica de retencion y genera un checkpoint de archivo."""
    client = _client(owner_id)
    try:
        project, _, _ = _resolve_or_create_project(
            client,
            project_id=project_id,
            owner_id=owner_id,
            create_if_missing=True,
        )
        policy = _table_upsert(
            client,
            "retention_policies",
            {
                "project_id": project["id"],
                "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                "keep_recent_sessions": keep_recent_sessions,
                "keep_recent_decisions": keep_recent_decisions,
                "archive_after_days": archive_after_days,
                "summarize_archived": summarize_archived,
            },
        )
        sessions = _sort_rows(_table_select(client, "sessions", {"project_id": project["id"]}))
        decisions = _sort_rows(_table_select(client, "decisions", {"project_id": project["id"]}))
        archive_candidates = {
            "sessions": [item.get("id") for item in sessions[keep_recent_sessions:]],
            "decisions": [item.get("id") for item in decisions[keep_recent_decisions:]],
        }
        checkpoint = None
        if summarize_archived:
            checkpoint = save_checkpoint(
                project_id=project["id"],
                owner_id=owner_id,
                title="Retention archive summary",
                architecture_summary="Archive candidates selected by retention policy.",
                functional_state=(
                    f"Sessions to archive: {len(archive_candidates['sessions'])}. "
                    f"Decisions to archive: {len(archive_candidates['decisions'])}."
                ),
                blockers=[],
                next_steps=["Review archive candidates before deletion or cold storage."],
                tags=["retention", "archive"],
            )
        _record_timeline(
            client,
            project["id"],
            owner_id or os.getenv("OWNER_ID", "default-owner"),
            "retention.applied",
            "Applied retention policy to project memory.",
            archive_candidates,
        )
        return {
            "status": "ok",
            "policy": policy,
            "archive_candidates": archive_candidates,
            "checkpoint": checkpoint.get("checkpoint") if checkpoint else None,
        }
    except Exception as exc:
        return {"error": str(exc), "tool": "apply_retention_policy"}


TOOL_HANDLERS: dict[str, Handler] = {
    "resolve_project": resolve_project,
    "create_project": create_project,
    "list_projects": list_projects,
    "load_unified_context": load_unified_context,
    "save_cross_interface_decision": save_cross_interface_decision,
    "update_task_status": update_task_status,
    "create_session": create_session,
    "end_session": end_session,
    "add_warning": add_warning,
    "get_active_warnings": get_active_warnings,
    "sync_session_state": sync_session_state,
    "get_interface_analytics": get_interface_analytics,
    "save_file_memory": save_file_memory,
    "save_checkpoint": save_checkpoint,
    "save_prompt_pattern": save_prompt_pattern,
    "capture_project_memory": capture_project_memory,
    "search_semantic_memory": search_semantic_memory,
    "get_project_timeline": get_project_timeline,
    "export_memory_bundle": export_memory_bundle,
    "import_memory_bundle": import_memory_bundle,
    "resume_project": resume_project,
    "apply_retention_policy": apply_retention_policy,
}


async def list_registered_tools() -> list[dict[str, Any]]:
    """Expone las herramientas soportadas por el servidor para tests locales."""
    return TOOL_SCHEMAS


async def call_registered_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ejecuta una herramienta por nombre para tests locales."""
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_HANDLERS[tool_name](**(arguments or {}))


setattr(server, "list_registered_tools", list_registered_tools)
setattr(server, "call_registered_tool", call_registered_tool)


def main() -> None:
    """Punto de entrada del servidor para ejecucion local o MCP stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
