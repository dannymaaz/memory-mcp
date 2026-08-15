# Upgrading Persistent Memory MCP

## Upgrade from 0.2.0 to 0.3.0

Version 0.3.0 introduces explicit local schema versioning. The upgrade is intentionally not automatic: an existing SQLite database must be previewed and explicitly migrated before the MCP server will start.

### Before upgrading

1. Stop every MCP client, editor integration and dashboard using the database.
2. Record the active SQLite path from your configuration. The default is `~/.memory-mcp/memory.db`.
3. Keep the existing 0.2.0 environment/configuration files.

### Install 0.3.0

For pipx:

```bash
pipx install --force persistent-memory-mcp==0.3.0
```

For a virtual environment:

```bash
python -m pip install --upgrade persistent-memory-mcp==0.3.0
```

### Preview the migration

Preview is read-only:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env
```

For the 0.2.0 baseline, the expected pending migration is version `1` (`v0_3_schema_baseline`). Do not apply a migration if the preview reports an unknown version, checksum/history error or incompatible database.

### Apply explicitly

After reviewing the preview:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env --apply --yes
```

The command creates a verified pre-migration SQLite backup before changing migration state. Preserve both the `.db` backup and its JSON manifest.

### Verify the upgraded installation

```bash
memory-mcp doctor --env ~/.memory-mcp/.env
memory-mcp health --env ~/.memory-mcp/.env --full
memory-mcp-migrate --env ~/.memory-mcp/.env
```

The final migration preview must report no pending migrations. Normal MCP startup also checks this state read-only and refuses to serve a stale existing database.

## Rollback to 0.2.0

Rollback should restore the pre-migration database before reinstalling 0.2.0, even though the v0.3 baseline migration is intentionally minimal. This keeps application code and recorded schema state aligned.

### 1. Stop all clients

Ensure no MCP process, dashboard or editor integration is using the SQLite database.

### 2. Verify the pre-migration backup while 0.3.0 is still installed

Use the backup path printed by `memory-mcp-migrate --apply --yes`:

```bash
python -c "from persistent_memory_mcp.maintenance import verify_backup_manifest; import sys; print(verify_backup_manifest(sys.argv[1]))" /path/to/pre-migration-....db
```

Do not continue if verification fails.

### 3. Preserve the current upgraded database

Keep a separate copy for diagnosis before restoring the old state. With all clients stopped:

```bash
python -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" ~/.memory-mcp/memory.db ~/.memory-mcp/pre-rollback-v0.3.db
```

### 4. Restore the verified pre-migration backup

Use SQLite's backup API rather than copying a live WAL database:

```bash
python -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" /path/to/pre-migration-....db ~/.memory-mcp/memory.db
```

Then verify SQLite integrity:

```bash
python -c "import sqlite3; c=sqlite3.connect(r'~/.memory-mcp/memory.db'); print(c.execute('pragma integrity_check').fetchall()); c.close()"
```

If your shell does not expand `~` inside the Python argument, pass the absolute path instead.

### 5. Reinstall 0.2.0

```bash
pipx install --force persistent-memory-mcp==0.2.0
```

or:

```bash
python -m pip install --force-reinstall persistent-memory-mcp==0.2.0
```

### 6. Verify before resuming clients

Run the 0.2.0 status/doctor commands available in your installation and confirm your expected project/task data is present before reconnecting editors.

## Failure behavior

- `memory-mcp-migrate` without `--apply` does not mutate the database.
- `--apply` without `--yes` refuses mutation.
- Existing stale databases are never silently marked current.
- MCP startup never automigrates.
- Migration application creates a verified backup before mutation.
- A failed individual migration is rolled back and is not recorded as applied.

## CI evidence

The 0.3.0 release candidate is validated by installing the pinned historical 0.2.0 repository baseline, creating actual SQLite project/task data, installing the candidate wheel, checking that the startup guard blocks the pending schema, applying the explicit backup-first migration and verifying that the original data remains. This flow runs on Ubuntu, Windows and macOS.
