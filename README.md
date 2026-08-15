<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">A local-first persistent project memory and context compiler for MCP-compatible development tools.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#context-packet-and-token-budgets">Context Packet</a> ·
  <a href="docs/ROADMAP.md">Roadmap</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

![Version](https://img.shields.io/badge/version-0.3.0-0A7D73)
![License](https://img.shields.io/badge/license-MIT-black)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-compatible-6C5CE7)
![Storage](https://img.shields.io/badge/storage-local%20SQLite-003B57?logo=sqlite&logoColor=white)

## What is Persistent Memory MCP?

Persistent Memory MCP is an open-source Model Context Protocol server that gives development assistants durable, searchable project memory. It stores architecture, technical decisions, tasks, warnings, repository evidence, checkpoints and session state in a private local database so compatible clients can continue work without repeatedly reconstructing the project from scratch.

The product is deliberately personal and local-first: one local installation, private SQLite by default, a localhost-only dashboard and project/owner isolation. Shared team workspaces, public remote dashboards and multi-user role models are outside the product scope.

The post-v0.3 direction goes beyond storing memory. Persistent Memory MCP is evolving into a **Context Compiler**: stored memories and repository evidence are filtered, ranked, compressed, verified and packed under a measurable token budget before they are delivered to an agent.

## Core capabilities

| Capability | Result |
|---|---|
| Cross-client project memory | Continue work across MCP-compatible development tools |
| Git-aware context | Bind memory to repository, branch, commit and working-tree evidence |
| Decisions, tasks and warnings | Preserve architecture, active work, risks and blockers |
| Sessions and checkpoints | Resume from a known implementation state |
| Hybrid search | Combine semantic and lexical retrieval with local fallback |
| **Context Packet v1** | Deliver versioned, provenance-aware context under a hard token budget |
| Verified local backup | Create WAL-safe SQLite backups with integrity validation |
| SHA-256 manifests | Detect changed or tampered backup files without exposing memory contents |
| Health diagnostics | Inspect SQLite integrity and maintenance readiness without mutation |
| Confirmed restore | Preview and explicitly confirm verified restores with safety backup/rollback |
| Versioned migrations | Upgrade local schema through backup-first, checksum-verified migrations |
| Confirmed deletion | Require exact preview + short-lived confirmation before destructive deletion |
| Private local dashboard | Inspect project state without exposing the service remotely |

## Quick start

### 1. Install

```bash
pipx install persistent-memory-mcp
```

For development:

```bash
git clone https://github.com/dannymaaz/memory-mcp.git
cd memory-mcp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Initialize the local installation

```bash
memory-mcp init
```

The setup command creates private configuration, initializes the local SQLite database and generates MCP configuration for supported clients. The default database is `~/.memory-mcp/memory.db`.

Supabase and PostgreSQL remain optional self-managed storage modes:

```bash
pip install "persistent-memory-mcp[supabase]"
pip install "persistent-memory-mcp[postgresql]"
```

### 3. Check the installation

```bash
memory-mcp doctor
memory-mcp status
memory-mcp health
```

For full SQLite integrity validation:

```bash
memory-mcp health --full
```

To include verified-backup readiness:

```bash
memory-mcp health --backup-dir ~/.memory-mcp/backups
```

### 4. Add it to an MCP client

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

The server uses stdio when launched by an MCP client. It can also be started manually with:

```bash
memory-mcp serve
```

## Context Packet and token budgets

The post-v0.3 Context Compiler introduces a stable **Context Packet v1** on the real optimized context-delivery path.

A packet records:

- contract version;
- current objective/intent;
- next safe action when explicitly available;
- provenance sources;
- verification state;
- requested hard token budget;
- final serialized token count;
- tokenizer identity and model when known;
- exact vs deterministic-fallback counting mode;
- selected, dropped, compressed and token-cost metrics per context block.

The packet is budgeted as a complete serialized response, not only as a sum of memory-item estimates. If removable context does not fit, the lowest-ranked items are dropped. Required control/project information is never silently removed; compilation fails closed if the mandatory packet cannot fit.

### Deterministic local fallback

A normal installation does **not** need a provider tokenizer. `deterministic-heuristic-v2` works offline and deterministically. For small context requests (including the existing 256-token contract), the packet switches to a compact control representation while retaining version, objective, sources, verification, token accounting and per-block metrics.

### Optional exact local reference

For model-aware local BPE counting and measurement:

```bash
pip install "persistent-memory-mcp[tokenizers]"
```

The optional extra uses `tiktoken` when the requested model/encoding is resolvable. If automatic model resolution is unavailable, the product retains the deterministic local fallback rather than requiring a remote service.

### Reproducible estimator measurements

PR #60 adds fixed Spanish and source-code fixtures plus `scripts/evaluate_tokenization.py`.

Current measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference tokens | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Python/source code | 138 | 140 | **1.45%** |

The CI guardrail allows at most 40% error on these initial fixtures; the current worst case is 15.94%. The reference-tokenizer packet suite runs on Ubuntu, Windows and macOS in addition to the normal Python 3.11–3.13 matrix.

## Upgrading from 0.2.0

Version 0.3.0 introduced explicit versioned SQLite migrations. Existing databases are never silently migrated on MCP startup.

Preview first:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env
```

Apply only after reviewing the plan:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env --apply --yes
```

The apply step creates a verified pre-migration backup before mutation. Keep that backup and JSON manifest until the upgraded installation has been verified.

See [docs/UPGRADING.md](docs/UPGRADING.md) for the complete upgrade and rollback procedure.

## Natural-language examples

```text
Resume this project and tell me where we left off.
Load only the context needed to continue the authentication refactor.
Save the architecture decision we just made.
Show active warnings before changing authentication.
Search project memory for the database migration decision.
Preview deleting these completed task records.
Preview restoring this verified SQLite backup.
```

## How it works

```text
MCP client A ─────┐
MCP client B ─────┼── Model Context Protocol ── Persistent Memory MCP
MCP client C ─────┘                                      │
                                                         ├─ local SQLite memory
                                                         ├─ Git/repository evidence
                                                         ├─ search + ranking
                                                         ├─ trust/provenance filters
                                                         └─ Context Packet compiler
                                                                  │
                                                                  └─ bounded agent context
```

The server resolves project context, retrieves structured memory/evidence, rejects expired or unsafe records, ranks what matters for the current intent, compresses oversized items and compiles the result under a hard budget.

## Main MCP tools

| Tool | Purpose |
|---|---|
| `resume_project` | Return a concise continuation brief |
| `capture_project_memory` | Save decisions, tasks, warnings, files and state together |
| `search_semantic_memory` | Search project memory by meaning with lexical fallback |
| `load_unified_context` | Return optimized project context through the Context Packet delivery path |
| `save_cross_interface_decision` | Preserve technical decisions across compatible local clients |
| `update_task_status` | Track work across sessions and clients |
| `sync_session_state` | Save current working state |
| `export_memory_bundle` | Export memory as JSON or Markdown |
| `plan_memory_deletion` | Preview exact deletion candidates and issue a short-lived confirmation |
| `execute_memory_deletion` | Execute only an unchanged, scoped and confirmed deletion plan |
| `plan_memory_restore` | Preview a verified SQLite restore |
| `execute_memory_restore` | Execute only the unchanged confirmed restore after a safety backup |

Operational CLI commands include `memory-mcp init`, `doctor`, `status`, `health`, `serve` and `memory-mcp-migrate`.

## Data-safety model

Persistent Memory MCP uses explicit, fail-closed maintenance contracts:

- backups use SQLite's backup API rather than copying a live file;
- successful backups must pass integrity validation;
- manifests include SHA-256 and bounded structural metadata, not stored memory contents;
- health diagnostics are read-only;
- restore uses plan → explicit confirmation → fresh safety backup → atomic replacement → validation → rollback on failure;
- migrations use read-only preview and verified pre-migration backup before explicit apply;
- startup refuses stale existing schemas rather than automigrating;
- deletion/retention uses exact plan fingerprints and short-lived confirmation;
- context-managed SQLite handles close deterministically after commit/rollback semantics.

## Privacy and product scope

- SQLite is the default local persistence backend.
- The dashboard binds to localhost only.
- Reads/writes are scoped by project and local owner identity.
- Sensitive values are redacted before persistence.
- Context compilation does not execute code.
- Optional exact token measurement runs locally; the fallback is provider-free.
- Team memberships, shared roles, billing and public collaborative dashboards are out of scope.

## Roadmap

The mandatory post-v0.3 order is:

1. **Context Packet + model-aware token accounting** — PR #60 / MEM-36, in review.
2. **Progressive repository retrieval** — repository map → file → symbol → exact fragment.
3. **Persistent code provenance and symbol evolution** across revisions.
4. **Context-quality regression guardrails** with measurable golden scenarios.
5. **Operational project map / Galaxy** built on verified retrieval/provenance data.

See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance criteria, sequencing rules and current evidence.

## Documentation

- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Delivery roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Upgrade and rollback](docs/UPGRADING.md)
- [Release operator checklist](docs/RELEASING.md)
- Public site: **https://dannymaaz.github.io/memory-mcp/**

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), open an issue or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Created and maintained by [Danny Maaz](https://github.com/dannymaaz).
