"""Automatic continuation checkpoints and repository-bound project resolution."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .security import redact_sensitive_value

CONTINUATION_VERSION = "1.0"
MAX_TEXT_LENGTH = 2_000
MAX_ITEMS = 20
MAX_ITEM_LENGTH = 512


def _bounded_text(value: Any, *, limit: int = MAX_TEXT_LENGTH) -> str:
    redacted = redact_sensitive_value(str(value or "")).value
    return str(redacted).strip()[:limit]


def _bounded_items(value: Any, *, limit: int = MAX_ITEMS) -> list[Any]:
    if value is None:
        values: list[Any] = []
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]

    compact: list[Any] = []
    for item in values[:limit]:
        if isinstance(item, Mapping):
            allowed = ("path", "file", "name", "status", "result", "summary")
            record = {
                key: _bounded_text(item.get(key), limit=MAX_ITEM_LENGTH)
                for key in allowed
                if item.get(key) not in (None, "")
            }
            if record:
                compact.append(record)
                continue
        text = _bounded_text(item, limit=MAX_ITEM_LENGTH)
        if text:
            compact.append(text)
    return compact


def _normalize_remote(value: Any) -> str:
    remote = str(value or "").strip().rstrip("/")
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@") and ":" in remote:
        host_path = remote[4:].replace(":", "/", 1)
        remote = host_path
    if remote.startswith("ssh://git@"):
        remote = remote[len("ssh://git@") :]
    for prefix in ("https://", "http://", "ssh://"):
        if remote.startswith(prefix):
            remote = remote[len(prefix) :]
            break
    return remote.casefold()


def _normalize_root(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return os.path.normcase(str(Path(raw).expanduser().resolve(strict=False)))
    except (OSError, RuntimeError):
        return os.path.normcase(os.path.abspath(os.path.expanduser(raw)))


def _root_fingerprint(value: Any) -> str:
    normalized = _normalize_root(value)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _project_binding_match(project: Mapping[str, Any], repo: Mapping[str, Any]) -> int:
    remote = _normalize_remote(repo.get("repo_remote"))
    root = _normalize_root(repo.get("repo_root"))
    project_remote = _normalize_remote(project.get("repo_remote"))
    project_root = _normalize_root(project.get("repo_path"))

    score = 0
    if remote and project_remote and remote == project_remote:
        score += 2
    if root and project_root and root == project_root:
        score += 1
    return score


def _find_bound_project(
    server_module: Any,
    client: Any,
    owner_id: str,
    repo: Mapping[str, Any],
) -> dict[str, Any] | None:
    projects = server_module._table_select(client, "projects", {"owner_id": owner_id})
    scored = [(_project_binding_match(project, repo), project) for project in projects]
    scored = [(score, project) for score, project in scored if score > 0]
    if not scored:
        return None

    best_score = max(score for score, _ in scored)
    best = [project for score, project in scored if score == best_score]
    if len(best) != 1:
        raise ValueError(
            "Ambiguous repository binding: multiple owner projects match the current repository"
        )
    return best[0]


def _continuation_repo(repo: Mapping[str, Any]) -> dict[str, Any]:
    changed = _bounded_items(repo.get("repo_status"))
    return {
        "branch": _bounded_text(repo.get("repo_branch"), limit=256),
        "commit": _bounded_text(repo.get("repo_commit"), limit=128),
        "dirty": bool(changed),
        "changed_files": changed,
        "remote": _bounded_text(_normalize_remote(repo.get("repo_remote")), limit=512),
        "root_fingerprint": _root_fingerprint(repo.get("repo_root")),
    }


def build_continuation_snapshot(
    *,
    session: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
    repo: Mapping[str, Any] | None,
    completed_work: str = "",
    remaining_work: Any = None,
    next_step: str = "",
    blockers: Any = None,
) -> dict[str, Any]:
    """Build a compact, redacted continuation contract from persisted session state."""
    session_data = dict(session or {})
    state_data = dict(state or {})
    session_metadata = dict(session_data.get("metadata") or {})

    objective = (
        state_data.get("objective")
        or state_data.get("current_goal")
        or session_metadata.get("current_goal")
        or ""
    )
    completed = (
        completed_work
        or state_data.get("what_was_done")
        or state_data.get("completed_work")
        or state_data.get("summary")
        or ""
    )
    pending_source = remaining_work
    if pending_source in (None, "", []):
        pending_source = state_data.get("remaining_work") or state_data.get("pending_items") or []
    blocker_source = blockers
    if blocker_source in (None, "", []):
        blocker_source = state_data.get("blockers") or []
    next_action = (
        next_step
        or state_data.get("next_step")
        or state_data.get("recommended_next_step")
        or ""
    )
    files = (
        state_data.get("files")
        or state_data.get("file_paths")
        or state_data.get("changed_files")
        or []
    )
    tests = state_data.get("tests") or state_data.get("test_results") or []

    snapshot = {
        "version": CONTINUATION_VERSION,
        "objective": _bounded_text(objective),
        "completed": _bounded_text(completed),
        "pending": _bounded_items(pending_source),
        "blockers": _bounded_items(blocker_source),
        "files": _bounded_items(files),
        "tests": _bounded_items(tests),
        "next_action": _bounded_text(next_action),
        "git": _continuation_repo(dict(repo or {})),
    }
    return redact_sensitive_value(snapshot).value


def _replace_tool(server_module: Any, name: str, function: Callable[..., Any]) -> None:
    tools = getattr(getattr(server_module, "server", None), "_tools", None)
    if isinstance(tools, dict):
        tools[name] = function
    handlers = getattr(server_module, "TOOL_HANDLERS", None)
    if isinstance(handlers, dict) and name in handlers:
        handlers[name] = function


def install_continuation_contract(server_module: Any) -> None:
    """Install repository binding plus a backward-compatible continuation contract."""
    if getattr(server_module, "_continuation_contract_installed", False):
        return

    original_resolve = server_module._resolve_or_create_project
    original_end = server_module.end_session
    original_resume = server_module.resume_project

    def resolve_or_create_project(
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
        if project_id:
            return original_resolve(
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
                description=description,
            )

        resolved_owner = owner_id or os.getenv("OWNER_ID", "default-owner")
        repo = server_module.detect_repo_context(repo_path).to_dict()
        if repo_url:
            repo["repo_remote"] = repo_url
        bound = _find_bound_project(server_module, client, resolved_owner, repo)
        if bound is not None:
            return original_resolve(
                client,
                project_id=str(bound["id"]),
                owner_id=resolved_owner,
                repo_path=repo_path,
                repo_url=repo_url,
                project_name=project_name,
                project_slug=project_slug,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                create_if_missing=False,
                description=description,
            )

        return original_resolve(
            client,
            project_id=None,
            owner_id=resolved_owner,
            repo_path=repo_path,
            repo_url=repo_url,
            project_name=project_name,
            project_slug=project_slug,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            create_if_missing=create_if_missing,
            description=description,
        )

    def end_session(
        session_id: str | None = None,
        project_id: str | None = None,
        owner_id: str | None = None,
        completed_work: str = "",
        remaining_work: str = "",
        next_step: str = "",
        blockers: list[str] | None = None,
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        try:
            project, _, repo = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                create_if_missing=True,
            )
            session = None
            if session_id:
                rows = server_module._table_select(client, "sessions", {"id": session_id})
                session = rows[0] if rows else None
            if session is None:
                session = server_module._find_active_session(client, project["id"])
            if session is None:
                raise ValueError("No active session available to end")

            state_rows = server_module._table_select(
                client, "session_state", {"session_id": session.get("id")}
            )
            state = state_rows[0].get("state", {}) if state_rows else {}
            snapshot = build_continuation_snapshot(
                session=session,
                state=state,
                repo=repo,
                completed_work=completed_work,
                remaining_work=remaining_work,
                next_step=next_step,
                blockers=blockers,
            )
            completed_value = completed_work or str(snapshot.get("completed") or "")
            pending_value = remaining_work or "; ".join(
                str(item) for item in snapshot.get("pending", []) if isinstance(item, str)
            )
            next_value = next_step or str(snapshot.get("next_action") or "")
            blocker_value = blockers if blockers is not None else list(snapshot.get("blockers", []))

            result = original_end(
                session_id=str(session.get("id")),
                project_id=project["id"],
                owner_id=owner_id,
                completed_work=completed_value,
                remaining_work=pending_value,
                next_step=next_value,
                blockers=[str(item) for item in blocker_value],
            )
            checkpoint_id = result.get("checkpoint_id") if isinstance(result, dict) else None
            if checkpoint_id and "error" not in result:
                rows = server_module._table_select(client, "checkpoints", {"id": checkpoint_id})
                checkpoint = rows[0] if rows else {}
                server_module._table_upsert(
                    client,
                    "checkpoints",
                    {
                        "id": checkpoint_id,
                        "project_id": project["id"],
                        "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                        "metadata": {
                            **(checkpoint.get("metadata") or {}),
                            "continuation": snapshot,
                        },
                    },
                )
                result["continuation"] = snapshot
            return result
        except Exception as exc:
            return {"error": str(exc), "tool": "end_session"}

    def resume_project(
        project_id: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        result = original_resume(project_id=project_id, owner_id=owner_id)
        if "error" in result:
            return result
        resume = result.get("resume") or {}
        resolved_project_id = resume.get("project_id") or project_id
        if not resolved_project_id:
            return result

        client = server_module._client(owner_id)
        checkpoints = server_module._sort_rows(
            server_module._table_select(client, "checkpoints", {"project_id": resolved_project_id})
        )
        latest = checkpoints[0] if checkpoints else {}
        continuation = (latest.get("metadata") or {}).get("continuation")
        if not isinstance(continuation, dict):
            repo = resume.get("repo") or {}
            continuation = build_continuation_snapshot(
                session=None,
                state={
                    "what_was_done": resume.get("what_was_done", ""),
                    "remaining_work": resume.get("what_is_left", []),
                    "next_step": resume.get("next_step", ""),
                },
                repo=repo,
                blockers=resume.get("warnings", []),
            )
        resume["continuation_version"] = CONTINUATION_VERSION
        resume["continuation"] = continuation
        result["resume"] = resume
        return result

    server_module._resolve_or_create_project = resolve_or_create_project
    server_module.end_session = end_session
    server_module.resume_project = resume_project
    _replace_tool(server_module, "end_session", end_session)
    _replace_tool(server_module, "resume_project", resume_project)
    server_module._continuation_contract_installed = True
