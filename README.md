<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">A local-first persistent project memory server for MCP-compatible development tools.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#upgrading-from-020">Upgrade from 0.2.0</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

![Version](https://img.shields.io/badge/version-0.3.0-0A7D73)
![License](https://img.shields.io/badge/license-MIT-black)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-compatible-6C5CE7)
![Storage](https://img.shields.io/badge/storage-local%20SQLite-003B57?logo=sqlite&logoColor=white)

## What is Persistent Memory MCP?

Persistent Memory MCP is an open-source Model Context Protocol server that gives development assistants durable, searchable project memory. It stores architecture, technical decisions, tasks, warnings, file relationships, checkpoints and session state in a private local database so another compatible client can continue the work without asking you to explain the project again.

The intended product is personal and local-first: one local installation, one private dashboard and isolated memory for the projects owned by that installation. Remote team workspaces, shared memberships and multi-user roles are intentionally outside the product scope.

> **Before:** “Can you explain the repository again?”  
> **After:** “The authentication refactor is in progress, RLS is the active risk, and the next task is token rotation.”

## Why developers use it

| Capability | Result |
|---|---|
| Cross-client memory | Continue work across compatible development tools |
| Git-aware context | Remember repository, branch, commit and working-tree state |
| Decisions and warnings | Preserve architectural reasoning, risks and blockers |
| Tasks and checkpoints | Resume from the exact implementation state |
| File-level memory | Understand important modules and dependencies |
| Semantic and lexical search | Find relevant context instead of loading everything |
| Confirmed deletion | Preview exact records and require a signed confirmation before deletion |
| Verified local backup | Create WAL-safe SQLite backups with integrity validation |
| SHA-256 manifests | Detect changed or tampered backup files without exposing memory contents |
| Health diagnostics | Check SQLite integrity and maintenance readiness without mutating data |
| Confirmed local restore | Preview and explicitly confirm verified SQLite restores with a safety backup and rollback |
| Versioned SQLite migrations | Upgrade local schema state with checksums, backup-first transactions and explicit user confirmation |
| Safe upgrade guard | Refuse MCP startup on a stale existing schema instead of silently automigrating |
| Private local dashboard | Inspect project memory without exposing it remotely |

## Quick start

### 1. Install

```bash
pipx install persistent-memory-mcp
```

For development installs:

```bash
git clone https://github.com/dannymaaz/memory-mcp.git
cd memory-mcp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Configure interactively

```bash
memory-mcp init
```

The setup command creates a private configuration, initializes the local SQLite database and generates an MCP configuration block for supported clients. The default local database is `~/.memory-mcp/memory.db`.

A genuinely new v0.3.0 SQLite database is initialized directly at the current packaged schema version and migration history. Existing databases are never marked current automatically.

Supabase and PostgreSQL remain available for advanced self-managed storage, but their drivers are optional extras rather than core dependencies:

```bash
pip install "persistent-memory-mcp[supabase]"
pip install "persistent-memory-mcp[postgresql]"
```

The core package and regression suite are validated on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13. Release CI builds the wheel and sdist, runs `twine check`, validates version metadata and SHA-256 checksums, installs the wheel in a clean environment and replays a real installed 0.2.0 → candidate upgrade on all three operating systems.

### 3. Diagnose the installation

```bash
memory-mcp doctor
memory-mcp status
memory-mcp health
```

For a full SQLite integrity check:

```bash
memory-mcp health --full
```

To include maintenance readiness based on verified backups, point the command at the directory containing backup manifests:

```bash
memory-mcp health --backup-dir ~/.memory-mcp/backups
```

`memory-mcp health` opens the active SQLite database read-only. It reports bounded `quick_check` results, optional `integrity_check`, foreign-key violations, expected-index gaps, database/WAL/SHM sizes, free disk space and the latest valid SHA-256 backup manifest without returning stored memory values or the absolute database path.

### 4. Add it to your MCP client

```json
{
  "mcpServers": {
    "persistent-memory-mcp": {
      "command": "memory-mcp",
      "env": {
        "MEMORY_BACKEND": "sqlite",
        "OWNER_ID": "your-stable-local-identifier",
        "MEMORY_CONFIRMATION_SECRET": "your-private-confirmation-secret"
      }
    }
  }
}
```

The command starts over stdio automatically when your MCP client launches it. You can also run it manually with `memory-mcp serve`.

## Upgrading from 0.2.0

Version 0.3.0 introduces explicit versioned SQLite migrations. Existing databases are **not** migrated on startup.

After installing 0.3.0, first preview the migration:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env
```

If the preview is expected, apply it explicitly:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env --apply --yes
```

The apply step creates a verified pre-migration backup before mutation. Keep the backup and its JSON manifest until the upgraded installation is verified.

If an existing SQLite database still has pending migrations, `memory-mcp serve` fails closed and tells you to run the preview/apply workflow; it never automigrates.

The release regression installs the pinned historical 0.2.0 package, creates real project/task data, installs the 0.3.0 candidate, confirms the startup guard rejects the stale schema, applies the explicit backup-first migration and verifies that the original data survives on Ubuntu, Windows and macOS.

See [docs/UPGRADING.md](docs/UPGRADING.md) for the full upgrade and rollback procedure.

## Natural-language examples

```text
Resume this project and tell me where we left off.
Save the architecture decision we just made.
Show active warnings before changing authentication.
Search project memory for the database migration decision.
Preview deletion of these completed task records.
Execute the unchanged deletion plan with its confirmation token.
Preview restoring this verified SQLite backup.
Execute the unchanged restore plan with its confirmation token.
```

## How it works

```text
MCP client A ─────┐
MCP client B ─────┼── Model Context Protocol ── Persistent Memory MCP ── Local SQLite
MCP client C ─────┘                                      │
                                                         ├─ decisions
                                                         ├─ tasks
                                                         ├─ warnings
                                                         ├─ sessions
                                                         ├─ file memory
                                                         └─ checkpoints
```

The server detects repository context, resolves or creates the current project, stores structured memories and returns an optimized resume context to compatible clients.

## Main MCP tools

| Tool | Purpose |
|---|---|
| `resume_project` | Return a concise continuation brief |
| `capture_project_memory` | Save decisions, tasks, warnings, files and state together |
| `search_semantic_memory` | Search by meaning with lexical fallback |
| `load_unified_context` | Load optimized project context |
| `save_cross_interface_decision` | Preserve technical decisions across local clients |
| `update_task_status` | Track work across sessions and clients |
| `sync_session_state` | Save the current working state |
| `export_memory_bundle` | Export memory as JSON or Markdown |
| `plan_memory_deletion` | Preview exact deletion candidates and issue a short-lived signed token |
| `execute_memory_deletion` | Execute only the unchanged, scoped and confirmed deletion plan |
| `plan_memory_restore` | Preview a verified restore and issue a short-lived confirmation tied to the exact plan |
| `execute_memory_restore` | Restore only the unchanged confirmed plan after creating a verified safety backup |

Operational CLI commands include `memory-mcp init`, `doctor`, `status`, `health`, `serve` and the explicit `memory-mcp-migrate` upgrade command.

Advanced MCP tools remain available for checkpoints, timelines, retention, prompts, analytics, embeddings, code intelligence and file relationships. Backup, health, confirmed restore and versioned migration services form the v0.3 local data-safety foundation.

## Confirmed deletion safety model

Deletion is a two-phase local operation:

1. `plan_memory_deletion` returns a dry-run preview, exact record IDs, counts, fingerprint, expiry and confirmation token.
2. `execute_memory_deletion` revalidates owner/project scope and current records, rejects altered, expired or reused plans, and deletes only exact planned IDs.

Retention cleanup uses the same preview-and-confirm contract. No retention deletion runs automatically at startup. Audit events record operation metadata and counts without copying deleted content.

## Backup, restore and migration safety model

PR #29 introduced consistent SQLite backup creation with `sqlite3.Connection.backup()` rather than direct filesystem copies. It supports active WAL mode, refuses accidental overwrite, validates the completed database with `PRAGMA integrity_check` and cleans incomplete temporary output after failures.

PR #35 adds a versioned JSON manifest to every successful backup with a SHA-256 digest, package/SQLite/schema versions, size, integrity result and bounded table counts. Manifest verification rejects changed or malformed backups without placing stored memory values or source database paths in the manifest.

PR #39 adds read-only SQLite health diagnostics so maintenance can verify the active database, structural indexes, foreign keys, storage headroom and available verified backups before destructive maintenance.

PR #43 introduced verified two-phase restore. A restore preview verifies the backup manifest, SHA-256, SQLite integrity, schema compatibility and disk headroom, then produces a short-lived confirmation bound to the exact plan. Execution creates a fresh verified safety backup before replacement, performs atomic replacement and automatically restores the safety backup if post-restore validation fails.

PR #46 hardened restore across Windows and macOS. Logical database drift is detected using a consistent WAL-aware SQLite snapshot fingerprint instead of relying on filesystem `mtime`/size changes. WAL/SHM cleanup tolerates only bounded transient handle-release delays and still fails closed when a persistent lock remains.

PR #45 added the versioned checksum-verified migration engine. PR #51 integrated it into the installed product with `memory-mcp-migrate`, a read-only startup guard and real package-upgrade validation. Planning is read-only, pending migrations create a verified pre-migration backup, and each migration runs transactionally and is recorded only after success.

PR #47 introduced validated immutable `RuntimeSettings`, with SQLite as the Settings default, `MEMORY_BACKEND` as the canonical backend variable, controlled deprecation of the historical alias and fail-closed conflicting aliases.

PR #52 makes context-managed SQLite connections close deterministically after native commit/rollback semantics, removing reliance on garbage collection for WAL/SHM handle release.

PR #41 validates actual built wheel/sdist installation. The v0.3 release gate additionally validates package version metadata, SHA-256 manifests and the installed historical 0.2.0 upgrade lifecycle.

## Privacy and security

- The dashboard binds only to localhost and rejects remote interfaces.
- The default database is a private SQLite file under the user's home directory.
- Every memory operation is scoped by owner and project.
- Sensitive values are redacted before persistence.
- Destructive operations require a short-lived confirmation tied to an exact plan.
- Backup manifests contain structural verification metadata, not memory values.
- Health diagnostics are read-only and expose bounded structural state rather than memory contents.
- Restore creates a verified safety backup before replacing the active database and can automatically roll back after failed validation.
- Existing pending migrations require explicit preview/apply and a verified pre-migration backup; startup never automigrates.
- Context-managed SQLite connections are closed deterministically after commit/rollback.
- Keep local configuration and confirmation secrets private.

## Product scope

Persistent Memory MCP is not a collaborative SaaS. Workspace invitations, team memberships, owner/admin/member/reader roles, public remote dashboards, billing and organization administration are out of scope.

## Roadmap

- [x] Persistent project, task, decision and warning memory
- [x] Git-aware project resolution foundation
- [x] Cross-client session continuity foundation
- [x] Semantic search with lexical fallback
- [x] Import, export, timeline and retention foundations
- [x] Interactive `init`, `doctor`, `status` and `health` commands
- [x] Local SQLite starter mode
- [x] Localhost-only visual memory dashboard
- [x] Automatic nested secret redaction
- [x] Provider-based embedding generation and reindexing
- [x] Selective deletion and confirmed retention execution
- [x] WAL-safe SQLite backup with integrity validation
- [x] Versioned SHA-256 backup manifests and tamper detection
- [x] SQLite health and maintenance-readiness diagnostics
- [x] Confirmed two-phase SQLite restore with safety backup and rollback
- [x] Versioned checksum-verified SQLite migrations
- [x] Explicit migration CLI and fail-closed startup guard
- [x] Real installed-package upgrade validation from 0.2.0 on Ubuntu, Windows and macOS
- [x] Centralized validated Settings foundation and safe legacy backend alias transition
- [x] Deterministic context-managed SQLite connection close semantics
- [x] SQLite-first core packaging with optional remote database extras
- [x] Ubuntu, Windows and macOS CI across Python 3.11–3.13
- [x] Wheel/sdist build, metadata check and clean-install validation on all three operating systems
- [x] v0.3.0 release notes and rollback documentation prepared
- [ ] Publish v0.3.0 GitHub Release and PyPI artifacts after final candidate validation
- [ ] MCP Registry release
- [ ] Dashboard pagination and operational summary cards
- [ ] Complete automatic continuation checkpoints

## Release documentation

- [Changelog](CHANGELOG.md)
- [Upgrade and rollback](docs/UPGRADING.md)
- [Release operator checklist](docs/RELEASING.md)

Public documentation covers installation, client configuration, architecture, data model, API reference, troubleshooting and English/Spanish guidance.

Visit: **https://dannymaaz.github.io/memory-mcp/**

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), open an issue, or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Created and maintained by [Danny Maaz](https://github.com/dannymaaz).
