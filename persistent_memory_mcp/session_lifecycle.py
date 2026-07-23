"""Automatic session lifecycle integration for the MCP runtime."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

DEFAULT_IDLE_MINUTES = 120


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def session_last_activity(session: dict[str, Any]) -> datetime | None:
    """Return the best available activity timestamp for a session."""
    metadata = session.get("metadata") or {}
    for value in (
        metadata.get("last_activity_at"),
        session.get("updated_at"),
        session.get("created_at"),
    ):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def session_is_stale(
    session: dict[str, Any],
    *,
    now: datetime | None = None,
    idle_minutes: int = DEFAULT_IDLE_MINUTES,
) -> bool:
    """Return whether an active session exceeded the configured idle window."""
    if idle_minutes < 1:
        raise ValueError("idle_minutes must be positive")
    last_activity = session_last_activity(session)
    if last_activity is None:
        return False
    current = (now or datetime.now(UTC)).astimezone(UTC)
    return current - last_activity >= timedelta(minutes=idle_minutes)


def _idle_minutes() -> int:
    raw = os.getenv("MEMORY_SESSION_IDLE_MINUTES", str(DEFAULT_IDLE_MINUTES))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MEMORY_SESSION_IDLE_MINUTES must be an integer") from exc
    if value < 1:
        raise ValueError("MEMORY_SESSION_IDLE_MINUTES must be positive")
    return value


def _server_now(server_module: Any) -> datetime:
    """Return the server clock so lifecycle decisions and persisted timestamps agree."""
    now_factory = getattr(server_module, "_now_iso", None)
    parsed = _parse_datetime(now_factory() if callable(now_factory) else None)
    return parsed or datetime.now(UTC)


def _replace_tool(server: Any, name: str, function: Callable[..., Any]) -> None:
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        tools[name] = function


def install_session_lifecycle(server_module: Any) -> None:
    """Install automatic create/reuse/handoff/heartbeat behavior on the server."""
    if getattr(server_module, "_automatic_session_lifecycle_installed", False):
        return

    original_create = server_module.create_session
    original_end = server_module.end_session
    original_sync = server_module.sync_session_state

    def create_session(
        project_id: str | None = None,
        interface: str | None = None,
        model_name: str | None = None,
        owner_id: str | None = None,
        repo_path: str | None = None,
        current_goal: str = "",
    ) -> dict[str, Any]:
        client = server_module._client(owner_id)
        try:
            project, _, _ = server_module._resolve_or_create_project(
                client,
                project_id=project_id,
                owner_id=owner_id,
                repo_path=repo_path,
                create_if_missing=True,
            )
            interface_name = interface or server_module.detect_interface()
            active = server_module._find_active_session(client, project["id"])
            if active is not None:
                stale = session_is_stale(
                    active,
                    now=_server_now(server_module),
                    idle_minutes=_idle_minutes(),
                )
                same_interface = active.get("interface") == interface_name
                if same_interface and not stale:
                    metadata = {
                        **(active.get("metadata") or {}),
                        "current_goal": current_goal
                        or (active.get("metadata") or {}).get("current_goal", ""),
                        "last_activity_at": server_module._now_iso(),
                    }
                    updated = server_module._table_upsert(
                        client,
                        "sessions",
                        {
                            "id": active.get("id"),
                            "project_id": project["id"],
                            "status": "active",
                            "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                            "metadata": metadata,
                        },
                    )
                    return {
                        "status": "ok",
                        "project_id": project.get("id"),
                        "session_id": updated.get("id"),
                        "interface": updated.get("interface") or interface_name,
                        "model_name": updated.get("model_name") or active.get("model_name"),
                        "reused": True,
                        "handoff": False,
                    }

                reason = "idle timeout" if stale else f"handoff to {interface_name}"
                original_end(
                    session_id=str(active.get("id")),
                    project_id=project["id"],
                    owner_id=owner_id,
                    completed_work=f"Session closed automatically: {reason}.",
                    next_step=current_goal,
                )

            result = original_create(
                project_id=project["id"],
                interface=interface_name,
                model_name=model_name,
                owner_id=owner_id,
                repo_path=repo_path,
                current_goal=current_goal,
            )
            if "error" not in result:
                result["reused"] = False
                result["handoff"] = active is not None
            return result
        except Exception as exc:
            return {"error": str(exc), "tool": "create_session"}

    def sync_session_state(
        session_id: str | None = None,
        project_id: str | None = None,
        state: dict[str, Any] | None = None,
        owner_id: str | None = None,
        summary: str = "",
    ) -> dict[str, Any]:
        resolved_session_id = session_id
        if resolved_session_id is None:
            created = create_session(project_id=project_id, owner_id=owner_id)
            if "error" in created:
                return created
            resolved_session_id = created.get("session_id")
        result = original_sync(
            session_id=resolved_session_id,
            project_id=project_id,
            state=state,
            owner_id=owner_id,
            summary=summary,
        )
        if "error" in result:
            return result
        client = server_module._client(owner_id)
        rows = server_module._table_select(client, "sessions", {"id": resolved_session_id})
        if rows:
            active = rows[0]
            server_module._table_upsert(
                client,
                "sessions",
                {
                    "id": active.get("id"),
                    "project_id": active.get("project_id") or project_id,
                    "status": "active",
                    "owner_id": owner_id or os.getenv("OWNER_ID", "default-owner"),
                    "metadata": {
                        **(active.get("metadata") or {}),
                        "last_activity_at": server_module._now_iso(),
                        "last_summary": summary,
                    },
                },
            )
        result["auto_created"] = session_id is None
        return result

    server_module.create_session = create_session
    server_module.sync_session_state = sync_session_state
    _replace_tool(server_module.server, "create_session", create_session)
    _replace_tool(server_module.server, "sync_session_state", sync_session_state)
    server_module._automatic_session_lifecycle_installed = True
