<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">A local-first persistent project memory server for MCP-compatible development tools.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

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

Supabase and PostgreSQL remain available for advanced self-managed storage, but their drivers are optional extras rather than core dependencies:

```bash
pip install "persistent-memory-mcp[supabase]"
pip install "persistent-memory-mcp[postgresql]"
```

The core package and regression suite are validated on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13.

### 3. Diagnose the installation

```bash
memory-mcp doctor
memory-mcp status
```

A richer `memory-mcp health` integrity report is tracked for v0.3.0 before restore and migration workflows are enabled.

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

## Natural-language examples

```text
Resume this project and tell me where we left off.
Save the architecture decision we just made.
Show active warnings before changing authentication.
Search project memory for the database migration decision.
Preview deletion of these completed task records.
Execute the unchanged deletion plan with its confirmation token.
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
| `execute_memory_deletion` | Execute only the unchanged, scoped and confirmed plan |

Advanced tools remain available for checkpoints, timelines, retention, prompts, analytics, embeddings, code intelligence and file relationships. Verified backup services currently live in the maintenance API while the v0.3 CLI/dashboard maintenance UX is completed.

## Confirmed deletion safety model

Deletion is a two-phase local operation:

1. `plan_memory_deletion` returns a dry-run preview, exact record IDs, counts, fingerprint, expiry and confirmation token.
2. `execute_memory_deletion` revalidates owner/project scope and current records, rejects altered, expired or reused plans, and deletes only exact planned IDs.

Retention cleanup uses the same preview-and-confirm contract. No retention deletion runs automatically at startup. Audit events record operation metadata and counts without copying deleted content.

## Verified backup safety model

PR #29 introduced consistent SQLite backup creation with `sqlite3.Connection.backup()` rather than direct filesystem copies. It supports active WAL mode, refuses accidental overwrite, validates the completed database with `PRAGMA integrity_check` and cleans incomplete temporary output after failures.

PR #35 adds a versioned JSON manifest to every successful backup with a SHA-256 digest, package/SQLite/schema versions, size, integrity result and bounded table counts. Manifest verification rejects changed or malformed backups without placing stored memory values or source database paths in the manifest.

Restore remains intentionally unavailable until the v0.3 two-phase restore workflow can validate the selected backup, preview the exact operation, create a fresh safety backup and require explicit confirmation.

## Privacy and security

- The dashboard binds only to localhost and rejects remote interfaces.
- The default database is a private SQLite file under the user's home directory.
- Every memory operation is scoped by owner and project.
- Sensitive values are redacted before persistence.
- Destructive operations require a short-lived confirmation tied to an exact plan.
- Backup manifests contain structural verification metadata, not memory values.
- Keep local configuration and confirmation secrets private.
- Create a verified backup before upgrades, migrations or destructive maintenance.

## Product scope

Persistent Memory MCP is not a collaborative SaaS. Workspace invitations, team memberships, owner/admin/member/reader roles, public remote dashboards, billing and organization administration are out of scope.

## Roadmap

- [x] Persistent project, task, decision and warning memory
- [x] Git-aware project resolution
- [x] Cross-client session continuity foundation
- [x] Semantic search with lexical fallback
- [x] Import, export, timeline and retention foundations
- [x] Interactive `init`, `doctor` and `status` commands
- [x] Local SQLite starter mode
- [x] Localhost-only visual memory dashboard
- [x] Automatic nested secret redaction
- [x] Provider-based embedding generation and reindexing
- [x] Selective deletion and confirmed retention execution
- [x] WAL-safe SQLite backup with integrity validation
- [x] Versioned SHA-256 backup manifests and tamper detection
- [x] SQLite-first core packaging with optional remote database extras
- [x] Ubuntu, Windows and macOS CI across Python 3.11–3.13
- [ ] `memory-mcp health` and integrity diagnostics
- [ ] Confirmed two-phase SQLite restore
- [ ] Versioned SQLite migrations and 0.2.0 upgrade validation
- [ ] Dashboard pagination and operational summary cards
- [ ] Complete automatic continuation checkpoints
- [ ] Wheel/sdist clean-install validation and release publication
- [ ] MCP Registry release

## Documentation

Public documentation covers installation, client configuration, architecture, data model, API reference, troubleshooting and English/Spanish guidance.

Visit: **https://dannymaaz.github.io/memory-mcp/**

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), open an issue, or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Created and maintained by [Danny Maaz](https://github.com/dannymaaz).
