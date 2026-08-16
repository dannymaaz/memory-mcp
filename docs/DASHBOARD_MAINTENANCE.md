# Local Dashboard maintenance contract

Persistent Memory MCP keeps the Dashboard **localhost-only and read-only by default**. PR #77 adds a deliberately narrow maintenance surface for operations that already have local safety contracts: verified backup, confirmed restore and confirmed selective deletion.

The Dashboard does not become a remote administration service. It does not accept arbitrary filesystem paths, does not expose raw SQL and does not bypass the existing confirmation services.

## Start the Dashboard

```bash
memory-mcp-dashboard \
  --sqlite-path ~/.memory-mcp/memory.db \
  --owner-id "$OWNER_ID" \
  --backup-dir ~/.memory-mcp/backups
```

`--backup-dir` is optional for status-only use. Backup and restore controls remain disabled in the UI until a backup directory is explicitly configured.

If `--owner-id` is omitted, owner inference is allowed only when the local database contains exactly one project owner. Zero or multiple owners fail closed for maintenance operations.

## Read-only status

```text
GET /api/maintenance/status
GET /api/maintenance/status?project_id=<id>
```

The status read model reuses `HealthService` and bounded aggregate queries. It reports:

- SQLite health and maintenance readiness;
- schema/SQLite/journal state;
- database, WAL and SHM sizes plus free disk space;
- latest verified backup metadata when `--backup-dir` is configured;
- persisted symbol/evidence verification-state counts;
- sensitivity aggregates from known owner-scoped tables.

It does not emit absolute database/backup paths or load source/memory bodies for these aggregates.

## Mutable maintenance endpoints

Every mutable route is `POST` only and requires:

```text
Content-Type: application/json
X-Memory-MCP-Action: 1
```

Request bodies are capped at **64 KiB**. Header names are treated case-insensitively as required by HTTP. Unsupported paths, fields, content types, malformed JSON and ambiguous owner scopes are rejected.

The custom header prevents normal cross-origin HTML form submissions from invoking localhost maintenance routes. The Dashboard page also uses a restrictive CSP with same-origin `connect-src` for its own `fetch()` calls. This is defense in depth for a localhost tool, not a replacement for keeping the service private.

### Create a verified backup

```text
POST /api/maintenance/backup
{}
```

The server generates the backup filename inside the configured `--backup-dir`. Clients cannot supply a destination path. The existing `BackupService` performs the SQLite backup, integrity validation and manifest/SHA-256 generation.

### Restore: preview, then confirm

```text
POST /api/maintenance/restore/plan
{
  "backup_name": "verified-backup.db"
}
```

Only a file name inside the configured backup directory is accepted. Path traversal and symbolic-link restore inputs are rejected. The preview verifies the backup and returns a short-lived signed confirmation bound to the exact restore plan.

Execution is a separate request:

```text
POST /api/maintenance/restore/execute
{
  "plan_id": "<exact-plan-fingerprint>",
  "confirmation_token": "<signed-token>"
}
```

Execution delegates to the existing `RestoreService`: it creates a fresh verified safety backup, performs the atomic replacement, validates the restored database and rolls back if post-restore validation fails. A consumed in-memory plan cannot be executed again through the Dashboard.

### Selective deletion: preview, then confirm

```text
POST /api/maintenance/delete/plan
{
  "memory_type": "tasks",
  "project_id": "<project-id>",
  "record_ids": ["<id-1>", "<id-2>"]
}
```

Deletion is limited to allow-listed memory tables, one owner/project scope and at most **100 explicit record IDs** per plan. The preview returns only the exact candidates that still exist in that scope plus a signed short-lived confirmation.

Execution is separate:

```text
POST /api/maintenance/delete/execute
{
  "plan": {"...": "exact previewed ForgetPlan"},
  "confirmation_token": "<signed-token>"
}
```

The Dashboard and MCP deletion interfaces share the same consumed-plan fingerprint set. A confirmation used through one interface is therefore consumed for the other as well.

## UI behavior

The localhost root page displays:

- health / maintenance readiness;
- database size and free disk headroom;
- latest verified backup state;
- evidence-risk count;
- sensitivity-tagged count;
- explicit empty/error states;
- backup action;
- restore preview + separate confirm action;
- deletion preview + separate confirm action.

Destructive confirm buttons begin disabled. The browser keeps the preview object in page memory and requires a second user action plus a native confirmation prompt before execution. Response text is written through `textContent`, not injected as response HTML.

## Security boundaries

The maintenance surface preserves these invariants:

1. Dashboard host remains loopback-only.
2. Owner/project scope is validated before scoped actions.
3. No arbitrary backup or restore destination paths are accepted.
4. Restore and deletion cannot execute without an unchanged signed preview.
5. Deletion confirmations are single-use across MCP and Dashboard interfaces.
6. Backup/restore/delete logic stays in the existing maintenance/retention services rather than raw HTTP-handler SQL.
7. Maintenance JSON/errors are bounded and avoid absolute filesystem paths.
8. The normal operational, Galaxy, snapshot and pagination routes remain read-only.

## Non-goals

PR #77 does **not** add:

- a public or remote Dashboard;
- collaborative accounts/roles;
- arbitrary SQL administration;
- arbitrary filesystem browsing;
- automatic restore or deletion;
- background maintenance jobs;
- a second backup/restore/delete implementation independent from the MCP safety contracts.
