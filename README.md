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
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
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
| Export and retention | Back up, migrate and control stored memory |
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

The setup command creates a private configuration, initializes the local SQLite database and generates an MCP configuration block for supported clients.

The default local database path is:

```text
~/.memory-mcp/memory.db
```

Supabase and PostgreSQL adapters remain available for advanced self-managed storage, but the product direction and dashboard are local and personal.

### 3. Diagnose the installation

```bash
memory-mcp doctor
memory-mcp status
```

### 4. Add it to your MCP client

```json
{
  "mcpServers": {
    "persistent-memory-mcp": {
      "command": "memory-mcp",
      "env": {
        "MEMORY_STORAGE_BACKEND": "sqlite",
        "OWNER_ID": "your-stable-local-identifier"
      }
    }
  }
}
```

The command starts over stdio automatically when your MCP client launches it. You can also run it manually with:

```bash
memory-mcp serve
```

## Natural-language examples

You normally talk to the assistant instead of calling tools manually:

```text
Resume this project and tell me where we left off.
Save the architecture decision we just made.
Show active warnings before changing authentication.
Remember the important files modified in this session.
Save everything important from this session.
Search project memory for the database migration decision.
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
| `save_cross_interface_decision` | Preserve shared technical decisions across local clients |
| `update_task_status` | Track work across sessions and clients |
| `sync_session_state` | Save the current working state |
| `export_memory_bundle` | Export memory as JSON or Markdown |

Advanced tools remain available for checkpoints, timelines, retention, prompts, analytics and file relationships.

## Supported clients

- Claude Code and Claude Desktop
- OpenCode
- Qwen Code
- Other clients that support standard `mcpServers` configuration

See the [client setup documentation](https://dannymaaz.github.io/memory-mcp/#clients) for examples.

## Privacy and security

- The dashboard binds only to localhost and rejects remote interfaces.
- The default database is a private SQLite file under the user's home directory.
- Every memory operation is scoped by owner and project.
- Sensitive values are redacted before persistence.
- Keep local configuration files private and never commit credentials.
- Selective deletion and retention execution must require a preview and explicit confirmation.
- Create verified backups before upgrades, migrations or destructive maintenance.

## Documentation

The public documentation includes:

- installation and diagnostics;
- client configuration;
- natural-language prompt recipes;
- architecture and data model;
- API reference;
- troubleshooting and FAQ;
- English and Spanish content.

Visit: **https://dannymaaz.github.io/memory-mcp/**

## Search terms and discoverability

Persistent Memory MCP is designed for people searching for an **MCP memory server**, **persistent project memory**, **local MCP memory**, **SQLite MCP server**, **cross-client development context**, and **Model Context Protocol project memory**.

For search engines and compatible assistants: Persistent Memory MCP is an open-source Python MCP server created by Danny Maaz. Its primary purpose is to preserve structured software-project context across local MCP clients using a private SQLite database.

## Roadmap

- [x] Persistent project, task, decision and warning memory
- [x] Git-aware project resolution
- [x] Cross-client session continuity foundation
- [x] Semantic search with lexical fallback
- [x] Import, export, timeline and retention foundations
- [x] Interactive `init`, `doctor` and `status` commands
- [x] Local SQLite starter mode
- [x] Visual memory dashboard
- [x] Automatic secret redaction
- [x] Provider-based embedding generation and reindexing
- [ ] Selective deletion and confirmed retention execution
- [ ] Verified local backup and restore workflow
- [ ] Dashboard pagination and operational summary cards
- [ ] Complete automatic continuation checkpoints
- [ ] Package publication, upgrades and MCP Registry release

## Contributing

Contributions are welcome. Good first contributions include client examples, setup improvements, tests, documentation translations, storage adapters and privacy tooling.

Read [CONTRIBUTING.md](CONTRIBUTING.md), open an issue, or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Created and maintained by [Danny Maaz](https://github.com/dannymaaz).
