<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">A local-first persistent project memory and context compiler for MCP-compatible development tools.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#context-packet-and-token-budgets">Context Packet</a> ·
  <a href="#progressive-repository-retrieval">Repository retrieval</a> ·
  <a href="#persistent-symbol-provenance-and-evolution">Symbol evolution</a> ·
  <a href="#context-quality-regression-guardrails">Quality gates</a> ·
  <a href="#operational-project-map-and-risk-oriented-galaxy">Operational map</a> ·
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

The post-v0.3 direction goes beyond storing memory. Persistent Memory MCP acts as a **Context Compiler**: stored memories and repository evidence are filtered, ranked, compressed, verified and packed under a measurable token budget before they are delivered to an agent. The operational map then projects the persisted evidence into a bounded risk-oriented view without loading full project content.

## Core capabilities

| Capability | Result |
|---|---|
| Cross-client project memory | Continue work across MCP-compatible development tools |
| Git-aware context | Bind memory to repository, branch, commit and working-tree evidence |
| Decisions, tasks and warnings | Preserve architecture, active work, risks and blockers |
| Sessions and checkpoints | Resume from a known implementation state |
| Hybrid search | Combine semantic and lexical retrieval with local fallback |
| **Context Packet v1** | Deliver versioned, provenance-aware context under a hard token budget |
| **Progressive repository retrieval** | Expand map → files → symbols → exact fragments instead of loading whole repositories |
| **Persistent symbol evolution** | Preserve logical symbol identity across commits, moves and safe rename matches with typed evidence |
| **Context quality regression gates** | Block retrieval, token-budget or provenance/safety regressions with deterministic local CI |
| **Operational project map** | View owner-scoped project risk, current changes and persisted evidence without loading full bodies |
| **Risk-oriented Galaxy** | Filter bounded project impact graphs by risk, verification state and current changes |
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

The Context Compiler exposes a stable **Context Packet v1** on the real optimized context-delivery path.

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

A normal installation does **not** need a provider tokenizer. `deterministic-heuristic-v2` works offline and deterministically. For small context requests, including the existing 256-token contract, the packet uses a compact control representation while retaining version, objective, sources, verification and token accounting.

### Optional exact local reference

```bash
pip install "persistent-memory-mcp[tokenizers]"
```

The optional extra uses `tiktoken` when the requested model/encoding is resolvable. If automatic model resolution is unavailable, the product keeps the deterministic local fallback rather than requiring a remote service.

Validated reference measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference tokens | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Python/source code | 138 | 140 | **1.45%** |

Quality #226 passed the complete Ubuntu/Windows/macOS × Python 3.11–3.13 delivery matrix.

## Progressive repository retrieval

PR #62 / MEM-37 exposes `retrieve_repository_context` through the real MCP runtime. Repository evidence expands progressively:

1. map supported repository paths with `git ls-files` without reading every file body;
2. rank candidate files using path evidence plus bounded local `git grep` signals;
3. parse symbols only from the bounded candidate set using the existing Python/TypeScript/JavaScript/SQL parsers;
4. expand bounded graph neighbors;
5. return exact selected line fragments instead of whole files.

Every fragment carries repository-relative path, line range, fragment SHA-256, file SHA-256 and Git commit/ref provenance. Recognized secrets are redacted before fragment content leaves the retrieval service.

The service rejects traversal/root escape, applies configured ignore patterns, never executes repository code and enforces explicit map/file/symbol/neighbor/byte/page/token limits. Cursor fingerprints include query, Git commit and candidate-file hashes so relevant committed or dirty changes invalidate stale cursors.

Reproducible PR #62 measurement:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Repository parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes emitted | **284 B** |
| Target fragment / file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

## Persistent symbol provenance and evolution

PR #64 / MEM-38 persists code-symbol history by Git commit instead of treating current parser output as timeless truth.

The symbol-evolution contract:

1. captures only a **clean Git HEAD**;
2. stores one idempotent run per owner/project/repository/commit;
3. persists bounded/redacted signatures plus signature/body/file hashes — not source bodies;
4. compares against the nearest persisted Git ancestor;
5. classifies `added`, `modified`, `moved`, `renamed`, `deleted` and `unchanged`;
6. preserves stable `logical_id` across exact moves and conservative unique rename matches;
7. records typed evidence to files, commits and tests, plus explicitly validated project decisions/tasks;
8. preserves evidence history when it becomes `stale`, `contradicted`, `missing_source` or `unverified`;
9. bounds history output with the Context Packet token-counter contract.

SQLite schema v2 adds `code_symbol_snapshot_runs`, `code_symbol_snapshots`, `code_symbol_changes` and `code_symbol_links`. Existing local databases receive migration `0002` through preview → verified backup → transactional apply.

The reference evaluation covers Python, TypeScript, JavaScript and SQL and validated **1 renamed, 1 moved and 2 modified** symbols while preserving rename identity. Quality #250 passed the exact PR #64 HEAD.

## Context quality regression guardrails

PR #66 / MEM-39 completed the fourth mandatory Context Compiler layer with deterministic local gates for retrieval quality, hard budget behavior and evidence safety. Quality #262 passed the exact final HEAD.

The versioned non-sensitive corpus measures:

- file recall@5 and precision@5;
- symbol recall@8 and precision@8;
- hard token-fit rate;
- token savings against a deterministic supported-repository baseline;
- provenance coverage;
- maximum task latency;
- hard safety pass rate.

Initial v1 baseline and gates:

| Metric | Baseline | CI gate |
|---|---:|---:|
| File recall@5 | **1.000** | ≥ **1.000** |
| File precision@5 | **0.200** | ≥ **0.200** |
| Symbol recall@8 | **1.000** | ≥ **1.000** |
| Symbol precision@8 | **0.125** | ≥ **0.125** |
| Token-fit rate | **1.000** | ≥ **1.000** |
| Token savings | **0.7722** | ≥ **0.400** |
| Provenance coverage | **1.000** | ≥ **1.000** |
| Safety pass rate | **1.000** | ≥ **1.000** |

Hard adversarial gates cover expired/untrusted memory, prompt injection, dirty cursor invalidation, rename identity continuity, contradicted evidence and dirty-Git stale evidence. Unit tests deliberately degrade recall, budget, savings, provenance, safety and latency and require threshold evaluation to fail.

```bash
pip install -e ".[tokenizers]"
python scripts/evaluate_context_quality.py
python scripts/evaluate_context_adversarial.py
```

See [docs/CONTEXT_QUALITY.md](docs/CONTEXT_QUALITY.md).

## Operational project map and risk-oriented Galaxy

PR #68 / MEM-40 adds a bounded operational projection over the existing SQLite project state and persisted code-symbol evidence. It does **not** add another repository scanner or graph database.

`OperationalMapService` provides:

- a global owner-scoped project overview;
- a per-project impact graph;
- project → repository → file → symbol relationships;
- verified symbol links to task/decision/file/test/deployment evidence where persisted;
- active tasks, blocked work and warnings;
- explicit `verified`, `stale`, `contradicted`, `missing_source` and `unverified` states;
- compact `critical`, `high`, `medium`, `low`, `none` risk projection;
- `changed_only` based only on the latest persisted snapshot run for each repository.

The changed-area view keeps changed files/symbols, their direct evidence neighbors and only the hierarchy needed to understand them. It does not fan out from a project node into unrelated work.

### Owner isolation and localhost endpoints

Operational owner resolution fails closed:

1. configured `--owner-id` / `OWNER_ID` wins;
2. without configuration, infer only when exactly one project owner exists;
3. zero or multiple owners are rejected instead of mixed.

New read-only localhost endpoints:

```text
GET /api/operational/projects
GET /api/operational/graph?project_id=<id>
GET /api/operational/export.json?project_id=<id>
GET /galaxy/operational?project_id=<id>
```

Project graphs support `verification`, `risk` and `changed_only` filters. Existing Dashboard/Galaxy endpoints remain compatible.

Operational payloads are deliberately compact: no full source/signature bodies, decision/task details, session/checkpoint bodies or absolute repository roots. Short display labels pass through the existing secret-redaction logic.

### Risk-oriented Galaxy

Operational Galaxy reuses the dependency-free renderer and adds:

- risk filter;
- verification-state filter;
- changed-only filter;
- visible critical/high/medium, stale and contradicted states;
- changed/missing/risk/verification summary counts;
- separate operational SVG/PNG exports;
- existing drag, zoom, focus, minimap and keyboard/ARIA behavior.

### Reproducible bounds and latency gate

`scripts/evaluate_operational_map.py` is wired into the Ubuntu/Windows/macOS reference CI jobs. Its local non-sensitive fixture contains 20 active-owner projects plus one foreign-owner project, 120 symbols across 12 files and 20 tasks.

Structural output:

| Metric | Result |
|---|---:|
| Overview projects | **20** |
| Full graph nodes | **154** |
| Full graph edges | **173** |
| Changed-area nodes | **55** |
| Changed-area edges | **74** |

Observed reference latency:

| Platform | Overview | Full graph | Changed-area graph |
|---|---:|---:|---:|
| Ubuntu | **3.04 ms** | **6.26 ms** | **4.35 ms** |
| Windows | **4.99 ms** | **8.08 ms** | **5.36 ms** |
| macOS | **5.65 ms** | **8.56 ms** | **4.15 ms** |

These are regression-fixture observations, not a production SLA. CI uses a deliberately non-flaky 5,000 ms ceiling and also requires owner isolation, hard bounds, read-only output, secret redaction, no absolute repository root, no full body fields and a genuinely reduced changed-area graph.

```bash
python scripts/evaluate_operational_map.py
```

See [docs/OPERATIONAL_MAP.md](docs/OPERATIONAL_MAP.md) for the complete public contract.

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
Find validate_token and return only the relevant source fragment with provenance.
Show the repository files and symbols relevant to the session implementation.
Capture the clean HEAD and persist how its symbols changed from the previous snapshot.
Show the history of finalize_order and whether its evidence is current, stale or contradicted.
Show which projects have stale or contradicted evidence.
Show the current affected area for this project without unrelated tasks.
Open the operational Galaxy for this project and filter to high-risk nodes.
Save the architecture decision we just made.
Preview deleting these completed task records.
Preview restoring this verified SQLite backup.
```

## How it works

```text
MCP client A ─────┐
MCP client B ─────┼── Model Context Protocol ── Persistent Memory MCP
MCP client C ─────┘                                      │
                                                         ├─ local SQLite memory
                                                         ├─ Git repository map
                                                         ├─ bounded file/symbol retrieval
                                                         ├─ persistent symbol history + typed evidence
                                                         ├─ provenance + trust filters
                                                         └─ Context Packet compiler
                                                                  │
                                                                  └─ bounded agent context

localhost Dashboard/Galaxy ── OperationalMapService ── persisted project/Git/symbol evidence
```

The MCP path resolves project context, rejects expired or unsafe records, ranks what matters for the current intent, progressively expands repository evidence and compiles the result under a hard token budget. The dashboard path is separate and read-only: it projects persisted evidence state into bounded operational views without independently re-running live Git verification on every request.

## Main MCP tools

| Tool | Purpose |
|---|---|
| `resume_project` | Return a concise continuation brief |
| `capture_project_memory` | Save decisions, tasks, warnings, files and state together |
| `search_semantic_memory` | Search project memory by meaning with lexical fallback |
| `load_unified_context` | Return optimized project context through the Context Packet path |
| `retrieve_repository_context` | Retrieve bounded repository map/file/symbol/fragment evidence |
| `capture_symbol_snapshot` | Persist the current clean Git HEAD symbol snapshot and evolution |
| `get_symbol_history` | Return bounded history, links and current evidence state |
| `compare_symbol_commits` | Compare classified symbol changes between persisted commits |
| `link_symbol_memory` | Link a logical symbol to a validated decision/task |
| `invalidate_symbol_evidence` | Mark evidence stale/contradicted/missing/unverified without deleting history |
| `save_cross_interface_decision` | Preserve technical decisions across compatible local clients |
| `update_task_status` | Track work across sessions and clients |
| `sync_session_state` | Save current working state |
| `export_memory_bundle` | Export memory as JSON or Markdown |
| `plan_memory_deletion` | Preview exact deletion candidates and issue a confirmation |
| `execute_memory_deletion` | Execute only an unchanged confirmed deletion plan |
| `plan_memory_restore` | Preview a verified SQLite restore |
| `execute_memory_restore` | Execute an unchanged confirmed restore after safety backup |

Operational CLI commands include `memory-mcp init`, `doctor`, `status`, `health`, `serve` and `memory-mcp-migrate`.

## Data-safety model

Persistent Memory MCP uses explicit fail-closed contracts:

- backups use SQLite's backup API rather than copying a live file;
- successful backups must pass integrity validation;
- manifests include SHA-256 and bounded structural metadata, not memory contents;
- health diagnostics are read-only;
- restore uses plan → confirmation → safety backup → atomic replacement → validation → rollback;
- migrations use read-only preview and verified backup before explicit apply;
- startup refuses stale existing schemas rather than automigrating;
- deletion/retention uses exact plan fingerprints and short-lived confirmation;
- repository retrieval is local/read-only, root-contained and fragment-bounded;
- persistent symbol capture requires a clean HEAD and refuses ambiguous speculative rename matches;
- Context Compiler quality gates fail on retrieval/budget/provenance/safety regressions;
- operational maps are owner-scoped, bounded, read-only and body-free;
- context-managed SQLite handles close deterministically after commit/rollback semantics.

## Privacy and product scope

- SQLite is the default local persistence backend.
- The dashboard binds to localhost only.
- Reads/writes are scoped by project and local owner identity.
- Operational owner inference is allowed only for a single-owner local database; ambiguous databases fail closed.
- Sensitive values are redacted before persistence and recognized secrets are redacted from emitted repository fragments and operational labels.
- Context compilation, repository retrieval, symbol-history capture and operational-map rendering do not execute repository code.
- Quality/performance evaluation uses synthetic non-sensitive fixtures and no remote telemetry/provider calls.
- Team memberships, shared roles, billing and public collaborative dashboards are out of scope.

## Roadmap

The mandatory post-v0.3 sequence is:

1. ✅ **Context Packet + model-aware token accounting** — PR #60 / MEM-36 / Quality #226.
2. ✅ **Progressive repository retrieval** — PR #62 / MEM-37 / Quality #235.
3. ✅ **Persistent code provenance and symbol evolution** — PR #64 / MEM-38 / Quality #250.
4. ✅ **Context-quality regression guardrails** — PR #66 / MEM-39 / Quality #262.
5. 🟡 **Operational project map / risk-oriented Galaxy** — PR #68 / MEM-40 in review.

See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance criteria, sequencing and current evidence.

## Documentation

- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Delivery roadmap](docs/ROADMAP.md)
- [Context Compiler quality evaluation](docs/CONTEXT_QUALITY.md)
- [Operational project map and Galaxy](docs/OPERATIONAL_MAP.md)
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