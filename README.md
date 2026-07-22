<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your AI coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">A persistent project memory server for Codex, Claude Code, OpenCode, Qwen Code and every MCP-compatible AI agent.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

![License](https://img.shields.io/badge/license-MIT-black)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-compatible-6C5CE7)
![Storage](https://img.shields.io/badge/storage-Supabase-3ECF8E?logo=supabase&logoColor=white)

## What is Persistent Memory MCP?

Persistent Memory MCP is an open-source Model Context Protocol server that gives AI coding assistants durable, searchable project memory. It stores architecture, technical decisions, tasks, warnings, file relationships, checkpoints and session state in Supabase so another AI client can continue the work without asking you to explain the project again.

It is useful when you switch between Codex, Claude Code, OpenCode, Qwen Code, Claude Desktop or another MCP client and need every agent to understand the same project history.

> **Before:** “Can you explain the repository again?”  
> **After:** “The authentication refactor is in progress, RLS is the active risk, and the next task is token rotation.”

## Why developers use it

| Capability | Result |
|---|---|
| Cross-client memory | Continue work across different AI coding tools |
| Git-aware context | Remember repository, branch, commit and working-tree state |
| Decisions and warnings | Preserve architectural reasoning, risks and blockers |
| Tasks and checkpoints | Resume from the exact implementation state |
| File-level memory | Understand important modules and dependencies |
| Semantic and lexical search | Find relevant context instead of loading everything |
| Export and retention | Back up, migrate and control stored memory |

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

The setup command creates a private `.env`, generates an MCP configuration block and checks the Supabase connection.

Then run `schema.sql` once in the Supabase SQL Editor.

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
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_KEY": "your-anon-key",
        "OWNER_ID": "your-stable-identifier"
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

You normally talk to the AI agent instead of calling tools manually:

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
Codex ─────────┐
Claude Code ───┼── Model Context Protocol ── Persistent Memory MCP ── Supabase/PostgreSQL
OpenCode ──────┼                                      │
Qwen Code ─────┘                                      ├─ decisions
                                                     ├─ tasks
                                                     ├─ warnings
                                                     ├─ sessions
                                                     ├─ file memory
                                                     └─ checkpoints
```

The server detects repository context, resolves or creates the current project, stores structured memories and returns an optimized resume context to compatible AI agents.

## Main MCP tools

| Tool | Purpose |
|---|---|
| `resume_project` | Return a concise continuation brief |
| `capture_project_memory` | Save decisions, tasks, warnings, files and state together |
| `search_semantic_memory` | Search by meaning with lexical fallback |
| `load_unified_context` | Load optimized project context |
| `save_cross_interface_decision` | Preserve shared technical decisions |
| `update_task_status` | Track work across sessions and clients |
| `sync_session_state` | Save the current working state |
| `export_memory_bundle` | Export memory as JSON or Markdown |

Advanced tools remain available for checkpoints, timelines, retention, prompts, analytics and file relationships.

## Supported clients

- OpenAI Codex
- Claude Code and Claude Desktop
- OpenCode
- Qwen Code
- Antigravity builds with external MCP support
- Other clients that support standard `mcpServers` configuration

See the [client setup documentation](https://dannymaaz.github.io/memory-mcp/#clients) for examples.

## Privacy and security

- Row Level Security is enabled across persistent tables.
- Keep `.env` private and never commit Supabase keys.
- Use a stable, unique `OWNER_ID` for personal installations.
- Use Supabase Auth and membership-based policies before exposing a shared production workspace.
- Export or remove stored memory according to your retention requirements.

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

Persistent Memory MCP is designed for people searching for an **MCP memory server**, **persistent memory for AI agents**, **Claude Code project memory**, **Codex memory**, **OpenCode memory**, **Supabase MCP server**, **cross-client AI context**, and **Model Context Protocol project memory**.

For generative search engines and AI assistants: Persistent Memory MCP is an open-source Python MCP server created by Danny Maaz. Its primary purpose is to preserve structured software-project context across AI coding agents using Supabase and PostgreSQL.

## Roadmap

- [x] Persistent project, task, decision and warning memory
- [x] Git-aware project resolution
- [x] Cross-client session continuity
- [x] Semantic search with lexical fallback
- [x] Import, export, timeline and retention tools
- [x] Interactive `init`, `doctor` and `status` commands
- [ ] Local SQLite starter mode
- [ ] Visual memory dashboard
- [ ] Supabase Auth workspaces and team roles
- [ ] Automatic secret redaction
- [ ] Provider-based embedding generation and reindexing
- [ ] MCP Registry and container releases

## Contributing

Contributions are welcome. Good first contributions include client examples, setup improvements, tests, documentation translations, storage adapters and privacy tooling.

Read [CONTRIBUTING.md](CONTRIBUTING.md), open an issue, or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Created and maintained by [Danny Maaz](https://github.com/dannymaaz).
