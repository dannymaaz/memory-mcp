"""Bounded HTTP adapter and UI controls for local Dashboard maintenance actions."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from .dashboard_actions import DashboardActionError, DashboardMaintenanceActions
from .maintenance.errors import MaintenanceError
from .retention import ALLOWED_MEMORY_TYPES, ConfirmationError
from .storage import SQLiteStorage

ACTION_HEADER = "X-Memory-MCP-Action"
ACTION_HEADER_VALUE = "1"
MAX_ACTION_BODY_BYTES = 64 * 1024

_ACTION_PATHS = frozenset(
    {
        "/api/maintenance/backup",
        "/api/maintenance/restore/plan",
        "/api/maintenance/restore/execute",
        "/api/maintenance/delete/plan",
        "/api/maintenance/delete/execute",
    }
)


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
        raise DashboardActionError(
            "maintenance owner is not configured and no project owner can be inferred"
        )
    raise DashboardActionError(
        "maintenance owner must be configured when multiple owners exist"
    )


def _expect_fields(
    payload: Mapping[str, Any],
    *,
    required: set[str] | frozenset[str] = frozenset(),
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    keys = set(payload)
    missing = sorted(set(required) - keys)
    unknown = sorted(keys - set(required) - set(optional))
    if missing:
        raise DashboardActionError(f"missing request field(s): {', '.join(missing)}")
    if unknown:
        raise DashboardActionError(f"unsupported request field(s): {', '.join(unknown)}")


def _ttl(payload: Mapping[str, Any]) -> int:
    raw = payload.get("confirmation_ttl_seconds", 300)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise DashboardActionError("confirmation_ttl_seconds must be an integer") from exc


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if "MEMORY_CONFIRMATION_SECRET" in message or "OWNER_ID is required" in message:
        return "A confirmation secret is required before destructive maintenance actions can run."
    if isinstance(exc, (DashboardActionError, ConfirmationError, MaintenanceError)) and message:
        return message[:300]
    return "The maintenance action request is invalid."


def dispatch_maintenance_action(
    storage: SQLiteStorage,
    *,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    owner_id: str | None,
    backup_directory: Path | None,
) -> tuple[int, dict[str, Any]]:
    """Validate one POST action and delegate to the existing safety services."""
    if path not in _ACTION_PATHS:
        return 404, {
            "status": "error",
            "error": "not_found",
            "message": "Unknown maintenance action.",
        }
    normalized_headers = {
        str(name).casefold(): str(value)
        for name, value in headers.items()
    }
    if normalized_headers.get(ACTION_HEADER.casefold(), "") != ACTION_HEADER_VALUE:
        return 403, {
            "status": "error",
            "error": "action_header_required",
            "message": f"{ACTION_HEADER}: {ACTION_HEADER_VALUE} is required.",
        }
    content_type = (
        normalized_headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type != "application/json":
        return 415, {
            "status": "error",
            "error": "json_required",
            "message": "Maintenance actions require application/json.",
        }
    if len(body) > MAX_ACTION_BODY_BYTES:
        return 413, {
            "status": "error",
            "error": "body_too_large",
            "message": "Maintenance action body is too large.",
        }
    try:
        decoded = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {
            "status": "error",
            "error": "invalid_json",
            "message": "Maintenance action body must be valid JSON.",
        }
    if not isinstance(decoded, dict):
        return 400, {
            "status": "error",
            "error": "object_required",
            "message": "Maintenance action body must be a JSON object.",
        }

    try:
        owner = _resolve_owner(storage, owner_id)
        actions = DashboardMaintenanceActions(
            storage,
            owner_id=owner,
            backup_directory=backup_directory,
        )
        if path == "/api/maintenance/backup":
            _expect_fields(decoded)
            return 200, actions.create_backup()
        if path == "/api/maintenance/restore/plan":
            _expect_fields(
                decoded,
                required={"backup_name"},
                optional={"confirmation_ttl_seconds"},
            )
            return 200, actions.plan_restore(
                backup_name=str(decoded["backup_name"]),
                confirmation_ttl_seconds=_ttl(decoded),
            )
        if path == "/api/maintenance/restore/execute":
            _expect_fields(decoded, required={"plan_id", "confirmation_token"})
            return 200, actions.execute_restore(
                plan_id=str(decoded["plan_id"]),
                confirmation_token=str(decoded["confirmation_token"]),
            )
        if path == "/api/maintenance/delete/plan":
            _expect_fields(
                decoded,
                required={"memory_type", "project_id", "record_ids"},
                optional={"confirmation_ttl_seconds"},
            )
            record_ids = decoded["record_ids"]
            if not isinstance(record_ids, list):
                raise DashboardActionError("record_ids must be a JSON array")
            return 200, actions.plan_deletion(
                memory_type=str(decoded["memory_type"]),
                project_id=str(decoded["project_id"]),
                record_ids=[str(item) for item in record_ids],
                confirmation_ttl_seconds=_ttl(decoded),
            )
        _expect_fields(decoded, required={"plan", "confirmation_token"})
        plan = decoded["plan"]
        if not isinstance(plan, dict):
            raise DashboardActionError("plan must be a JSON object")
        return 200, actions.execute_deletion(
            plan=plan,
            confirmation_token=str(decoded["confirmation_token"]),
        )
    except (DashboardActionError, ConfirmationError, MaintenanceError, ValueError, TypeError) as exc:
        return 400, {
            "status": "error",
            "error": "maintenance_action_rejected",
            "message": _safe_error_message(exc),
        }
    except Exception:
        return 500, {
            "status": "error",
            "error": "maintenance_action_failed",
            "message": "The maintenance action could not be completed safely.",
        }


def render_maintenance_controls(
    maintenance: Mapping[str, Any] | None,
    *,
    project_id: str | None,
) -> str:
    """Render local controls that always use preview/confirm for destructive actions."""
    backup = (maintenance or {}).get("backup", {}) if maintenance else {}
    backup_configured = bool(backup.get("configured"))
    disabled = "" if backup_configured else " disabled"
    project = html.escape(str(project_id or ""), quote=True)
    options = "".join(
        f'<option value="{html.escape(memory_type, quote=True)}">{html.escape(memory_type)}</option>'
        for memory_type in sorted(ALLOWED_MEMORY_TYPES)
    )
    backup_note = (
        "Verified backup directory is configured."
        if backup_configured
        else "Start the Dashboard with --backup-dir to enable backup and restore controls."
    )
    return (
        '<section class="maintenance-actions" aria-labelledby="maintenance-actions-heading">'
        '<h2 id="maintenance-actions-heading">Maintenance actions</h2>'
        '<p class="muted">Destructive actions require a signed preview and a separate confirmation.</p>'
        f'<p class="muted">{html.escape(backup_note)}</p>'
        '<div class="action-grid">'
        '<article><h3>Backup</h3><p>Create a verified SQLite backup with a server-generated name.</p>'
        f'<button type="button" id="maintenance-backup"{disabled}>Create verified backup</button></article>'
        '<article><h3>Restore</h3><label for="restore-backup-name">Backup file name</label>'
        f'<input id="restore-backup-name" placeholder="backup.db"{disabled}>'
        f'<button type="button" id="restore-preview"{disabled}>Preview restore</button>'
        '<button type="button" id="restore-confirm" disabled>Confirm restore</button></article>'
        '<article><h3>Delete selected memory</h3>'
        '<label for="delete-memory-type">Memory type</label>'
        f'<select id="delete-memory-type">{options}</select>'
        '<label for="delete-project-id">Project ID</label>'
        f'<input id="delete-project-id" value="{project}" placeholder="Project ID">'
        '<label for="delete-record-ids">Record IDs, comma separated</label>'
        '<input id="delete-record-ids" placeholder="id-1, id-2">'
        '<button type="button" id="delete-preview">Preview deletion</button>'
        '<button type="button" id="delete-confirm" disabled>Confirm deletion</button></article>'
        '</div><pre id="maintenance-action-status" class="action-status" role="status" aria-live="polite">Ready.</pre>'
        '<script>'
        '(()=>{const status=document.getElementById("maintenance-action-status");'
        'const headers={"Content-Type":"application/json","X-Memory-MCP-Action":"1"};'
        'let restorePlan=null;let deletePlan=null;'
        'const show=(value)=>{status.textContent=typeof value==="string"?value:JSON.stringify(value,null,2);};'
        'async function post(path,payload){show("Loading…");const response=await fetch(path,{method:"POST",headers,body:JSON.stringify(payload)});'
        'let data={status:"error",message:"Invalid response."};try{data=await response.json();}catch(_error){}'
        'if(!response.ok){throw new Error(data.message||"Maintenance action failed.");}return data;}'
        'const backup=document.getElementById("maintenance-backup");if(backup){backup.addEventListener("click",async()=>{try{show(await post("/api/maintenance/backup",{}));}catch(error){show("Error: "+error.message);}});}'
        'const restorePreview=document.getElementById("restore-preview");const restoreConfirm=document.getElementById("restore-confirm");'
        'if(restorePreview){restorePreview.addEventListener("click",async()=>{try{restorePlan=await post("/api/maintenance/restore/plan",{backup_name:document.getElementById("restore-backup-name").value});restoreConfirm.disabled=false;show({status:"preview",backup_name:restorePlan.backup_name,backup_size_bytes:restorePlan.backup_size_bytes,expires_at:restorePlan.expires_at});}catch(error){restorePlan=null;restoreConfirm.disabled=true;show("Error: "+error.message);}});}'
        'if(restoreConfirm){restoreConfirm.addEventListener("click",async()=>{if(!restorePlan){return;}if(!window.confirm("Restore this verified backup? A safety backup will be created first.")){return;}try{const result=await post("/api/maintenance/restore/execute",{plan_id:restorePlan.plan_id,confirmation_token:restorePlan.confirmation_token});restorePlan=null;restoreConfirm.disabled=true;show(result);}catch(error){show("Error: "+error.message);}});}'
        'const deletePreview=document.getElementById("delete-preview");const deleteConfirm=document.getElementById("delete-confirm");'
        'if(deletePreview){deletePreview.addEventListener("click",async()=>{try{const ids=document.getElementById("delete-record-ids").value.split(",").map(value=>value.trim()).filter(Boolean);deletePlan=await post("/api/maintenance/delete/plan",{memory_type:document.getElementById("delete-memory-type").value,project_id:document.getElementById("delete-project-id").value,record_ids:ids});deleteConfirm.disabled=deletePlan.candidate_count<1;show({status:"preview",candidate_count:deletePlan.candidate_count,missing_record_ids:deletePlan.missing_record_ids,expires_at:deletePlan.plan.expires_at});}catch(error){deletePlan=null;deleteConfirm.disabled=true;show("Error: "+error.message);}});}'
        'if(deleteConfirm){deleteConfirm.addEventListener("click",async()=>{if(!deletePlan){return;}if(!window.confirm("Permanently delete the records in this signed preview?")){return;}try{const result=await post("/api/maintenance/delete/execute",{plan:deletePlan.plan,confirmation_token:deletePlan.confirmation_token});deletePlan=null;deleteConfirm.disabled=true;show(result);}catch(error){show("Error: "+error.message);}});}'
        '})();</script></section>'
    )
