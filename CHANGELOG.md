# Changelog

All notable changes to Persistent Memory MCP are documented here.

## 0.3.0 — Data Safety and Recovery — 2026-08-15

Persistent Memory MCP 0.3.0 turns the local-first SQLite path into a recoverable, upgradeable and release-validated product. The release deliberately prioritizes data protection, explicit destructive actions and cross-platform reliability over new collaborative or visual features.

### Added

- WAL-safe SQLite backups using `sqlite3.Connection.backup()` instead of copying a live database file.
- Versioned JSON backup manifests with SHA-256, schema/package metadata, integrity result and bounded table counts.
- `memory-mcp health` with read-only `quick_check`, optional full `integrity_check`, foreign-key/index checks, DB/WAL/SHM sizes, free-space reporting and verified-backup awareness.
- Two-phase verified SQLite restore with preview, HMAC-bound short-lived confirmation, mandatory pre-restore safety backup, atomic replacement, post-restore validation and automatic rollback.
- WAL-aware logical database fingerprints for restore drift detection.
- Versioned checksum-verified SQLite migrations with read-only planning, `schema_migrations`, verified backup before mutation and transaction-per-migration execution.
- Installed `memory-mcp-migrate` command. Preview is the default; mutation requires `--apply --yes`.
- Read-only startup guard that refuses to serve an existing SQLite database while versioned migrations are pending. Startup never automigrates.
- Safe bootstrap of migration history for genuinely new empty SQLite databases.
- Pydantic `RuntimeSettings` with SQLite default, canonical `MEMORY_BACKEND`, transitional `MEMORY_STORAGE_BACKEND` warning, fail-closed conflicting aliases and masked secrets.
- Real wheel/sdist clean-install validation on Ubuntu, Windows and macOS.
- Real installed-package upgrade validation from the pinned 0.2.0 repository baseline on Ubuntu, Windows and macOS.

### Changed

- SQLite is the normal local installation path; Supabase and PostgreSQL drivers are optional extras.
- The MCP Python SDK is constrained to the supported v1 line (`mcp>=1.28,<2`) so v0.3.0 uses its real `FastMCP` server implementation; MCP v2 migration is deferred to a deliberate later compatibility change.
- CI covers Python 3.11, 3.12 and 3.13 on Ubuntu, Windows and macOS.
- CLI status markers use portable ASCII output (`[ok]`, `[error]`, `[skip]`) so redirected Windows consoles do not fail under CP1252.
- `SQLiteStorage` context-managed connections now preserve native commit/rollback semantics and close deterministically at context exit.
- Restore no longer treats filesystem `mtime`/size alone as semantic database drift; the WAL-aware logical SQLite snapshot is authoritative.
- WAL/SHM cleanup uses bounded retry behavior and still fails closed on persistent locks.

### Safety guarantees

- Backup creation refuses same-source/destination paths and accidental overwrite and cleans incomplete temporary output.
- Backup verification rejects changed, malformed or incompatible manifests without storing memory contents in the manifest.
- Restore never runs automatically and cannot execute an altered, expired or reused plan.
- Restore creates a verified safety backup immediately before replacement and rolls it back automatically after failed post-replacement validation.
- Migration preview is read-only. Existing databases are never marked current automatically.
- Pending migrations require an explicit user action and a verified pre-migration backup.
- Migration history rejects changed checksums, duplicate/non-positive versions, future schema versions and inconsistent `user_version`/history states.

### Upgrade from 0.2.0

1. Stop all clients using Persistent Memory MCP.
2. Install 0.3.0.
3. Review the database upgrade without mutation:

   ```bash
   memory-mcp-migrate --env ~/.memory-mcp/.env
   ```

4. If the preview is expected, apply it explicitly:

   ```bash
   memory-mcp-migrate --env ~/.memory-mcp/.env --apply --yes
   ```

5. Keep the reported pre-migration backup and its JSON manifest until the upgraded installation has been verified.
6. Run:

   ```bash
   memory-mcp doctor
   memory-mcp health --full
   ```

The release CI builds and installs the historical 0.2.0 package, creates real data, installs the 0.3.0 candidate, verifies that startup refuses the stale schema, applies the explicit migration with a verified backup and confirms the original data survives on all three supported operating systems.

### Known partial areas

These are not regressions and are not release blockers for the local personal product:

- automatic project resolution/continuation remains partial;
- persistent code-symbol history across revisions remains partial;
- dashboard pagination, operational summary cards and maintenance controls remain planned refinements;
- some provider/subsystem-specific environment variables remain direct configuration inputs even though backend/path/startup decisions use `RuntimeSettings`;
- team workspaces, memberships, role hierarchies and a public remote collaborative dashboard are intentionally out of scope.

## 0.2.0

0.2.0 is the compatibility baseline used by the v0.3.0 upgrade regression. It contains the local SQLite foundation, project memory primitives and the pre-v0.3 schema state without versioned migration history.
