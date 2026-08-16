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
| **Progressive repository retrieval** | Expand map → files → symbols → exact fragments instead of loading whole repositories |
| **Persistent symbol evolution** | Preserve logical symbol identity across commits, moves and safe rename matches with typed evidence |
| **Context quality regression gates** | Block retrieval, token-budget or provenance/safety regressions with deterministic local CI |
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

PR #60 added fixed Spanish and source-code fixtures plus `scripts/evaluate_tokenization.py`.

Validated measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference tokens | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Python/source code | 138 | 140 | **1.45%** |

The CI guardrail allows at most 40% error on these initial fixtures; the validated worst case is 15.94%. Context Packet/tokenizer reference jobs run on Ubuntu, Windows and macOS in addition to the normal Python 3.11–3.13 matrix.

## Progressive repository retrieval

PR #62 / MEM-37 implements the second Context Compiler layer through the real MCP runtime as `retrieve_repository_context`.

The retrieval path is intentionally progressive:

1. map supported repository paths with `git ls-files` without reading every file's content;
2. rank candidate files using path evidence plus bounded local `git grep` signals;
3. parse symbols only from the bounded candidate set using the existing Python/TypeScript/JavaScript/SQL code-intelligence parsers;
4. expand bounded graph neighbors;
5. read only the selected symbol fragments and return exact line ranges instead of whole files.

Every returned fragment carries repository-relative path, start/end lines, fragment SHA-256, whole-file SHA-256 and Git commit/ref provenance. Recognized secrets are redacted before fragment content leaves the retrieval service.

### Retrieval safety and limits

The retrieval service:

- rejects absolute paths, traversal and resolved paths outside the repository root;
- applies `RuntimeSettings.ignore_patterns` together with existing code-intelligence excludes;
- never executes repository code;
- limits mapped files, parsed files, symbols, graph neighbors, file bytes, total fragment bytes, fragment lines, page size and token budget;
- binds pagination cursors to the query, commit and hashes of ranked candidate files so committed or relevant dirty-working-tree changes invalidate stale cursors;
- uses the same Context Packet token-counter contract instead of a separate estimator;
- trims low-priority retrieval payload sections until the final serialized response fits the requested token budget, and fails closed if mandatory control metadata alone cannot fit.

### Reproducible progressive-retrieval measurement

`scripts/evaluate_repository_retrieval.py` creates a deterministic synthetic repository and verifies that retrieval remains bounded.

Validated PR #62 measurement:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Repository parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes emitted | **284 B** |
| Target file lines | **125** |
| Target fragment lines | **7** |
| Target fragment / file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

The top ranked file and top fragment are both the intended `services/security.py` target. The evaluation is executed in CI on Ubuntu, Windows and macOS alongside the Context Packet reference jobs.

## Persistent symbol provenance and evolution

PR #64 / MEM-38 adds the third mandatory Context Compiler layer for local SQLite installations. It persists code-symbol history by Git commit instead of treating the current parser output as timeless truth.

The symbol-evolution contract:

1. captures only a **clean Git HEAD** and refuses a dirty working tree;
2. stores one idempotent snapshot run per owner/project/repository/commit;
3. persists bounded, redacted signatures plus signature/body/file SHA-256 values — not source bodies;
4. compares the current snapshot to the nearest persisted Git ancestor;
5. classifies symbols as `added`, `modified`, `moved`, `renamed`, `deleted` or `unchanged`;
6. preserves a stable `logical_id` across exact moves and conservative, unique rename matches;
7. records typed evidence to files, commits and detected tests, and supports explicitly validated links to project decisions/tasks;
8. keeps evidence history when a link becomes `stale`, `contradicted`, `missing_source` or `unverified` instead of deleting it;
9. bounds history output with the same Context Packet token-counter contract.

Rename matching is deliberately fail-safe. Exact qualified-name/body matches are preferred; a name-only rename may retain identity only when its normalized bounded signature is unique on both sides. Ambiguous candidates remain separate identities rather than being merged speculatively.

SQLite schema v2 adds `code_symbol_snapshot_runs`, `code_symbol_snapshots`, `code_symbol_changes` and `code_symbol_links`. Existing local databases receive migration `0002` through the normal preview → verified backup → transactional apply path. Fresh databases bootstrap migrations 1 and 2 directly.

### Reproducible symbol-evolution measurement

`scripts/evaluate_symbol_evolution.py` builds a deterministic two-commit repository containing Python, TypeScript, JavaScript and SQL, then captures and compares both commits.

The reference evaluation asserts all of the following:

| Check | Expected result |
|---|---:|
| Languages observed | **Python, TypeScript, JavaScript, SQL** |
| Rename preserves logical identity | **true** |
| Rename classified | **≥ 1** |
| Move classified | **≥ 1** |
| Modification classified | **≥ 1** |
| Current renamed symbol state | **verified** |

The validated delivery classified **1 renamed, 1 moved and 2 modified** symbols while preserving the renamed Python symbol's `logical_id`. Quality #250 passed the exact PR #64 HEAD across Ubuntu, Windows and macOS, Python 3.11–3.13, release-artifact upgrade and dependency audit. PR #64 / MEM-38 are complete.

## Context quality regression guardrails

PR #66 / MEM-39 adds the fourth mandatory Context Compiler layer: deterministic local gates for retrieval quality, hard budget behavior and evidence safety.

The quality suite uses a versioned, non-sensitive coding-task corpus and the **real** `ProgressiveRepositoryRetriever` path. Every evaluation records fixture/evaluator/threshold version, tokenizer identity and model identity when applicable.

Metrics include:

- file recall@5 and precision@5;
- symbol recall@8 and precision@8;
- hard token-fit rate;
- token savings against a deterministic supported-repository baseline;
- provenance coverage for expected evidence;
- maximum task latency;
- hard safety pass rate.

Initial deterministic v1 baseline and gates:

| Metric | Observed baseline | CI gate |
|---|---:|---:|
| File recall@5 | **1.000** | ≥ **1.000** |
| File precision@5 | **0.200** | ≥ **0.200** |
| Symbol recall@8 | **1.000** | ≥ **1.000** |
| Symbol precision@8 | **0.125** | ≥ **0.125** |
| Token-fit rate | **1.000** | ≥ **1.000** |
| Token savings | **0.7722** | ≥ **0.400** |
| Provenance coverage | **1.000** | ≥ **1.000** |
| Safety pass rate | **1.000** | ≥ **1.000** |
| Maximum task latency | **~149 ms** on first reference run | ≤ **20,000 ms** |

The initial precision floors protect the current baseline; they are not claims that ranking is already optimal. Retrieval improvements may raise them, but recall, hard budget, provenance and safety cannot regress silently.

Hard adversarial gates require all of the following:

- expired memory is excluded;
- prompt-injection/untrusted memory is excluded by default;
- relevant dirty repository changes invalidate stale retrieval cursors;
- a uniquely supported rename preserves logical symbol identity and is classified as a rename;
- contradicted evidence remains retained and visibly contradicted;
- dirty Git state marks previously current symbol evidence `stale`.

Unit tests also deliberately degrade recall, token fit, savings, provenance, safety and latency and require threshold evaluation to fail. The reference Quality jobs run the quality evaluator and adversarial evaluator on Ubuntu, Windows and macOS.

To reproduce locally from a development checkout:

```bash
pip install -e ".[tokenizers]"
python scripts/evaluate_context_quality.py
python scripts/evaluate_context_adversarial.py
```

See [docs/CONTEXT_QUALITY.md](docs/CONTEXT_QUALITY.md) for the public evaluation contract, thresholds and interpretation.

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

Post-v0.3 development may add later numbered migrations. The same command previews every pending version and applies it only after explicit confirmation and a verified backup.

See [docs/UPGRADING.md](docs/UPGRADING.md) for the complete upgrade and rollback procedure.

## Natural-language examples

```text
Resume this project and tell me where we left off.
Load only the context needed to continue the authentication refactor.
Find validate_token and return only the relevant source fragment with provenance.
Show the repository files and symbols relevant to the session implementation.
Capture the clean HEAD and persist how its symbols changed from the previous snapshot.
Show the history of finalize_order and whether its evidence is current, stale or contradicted.
Compare persisted symbol changes between these two commits.
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
                                                         ├─ Git repository map
                                                         ├─ bounded file/symbol retrieval
                                                         ├─ persistent symbol history + typed evidence
                                                         ├─ provenance + trust filters
                                                         └─ Context Packet compiler
                                                                  │
                                                                  └─ bounded agent context
```

The server resolves project context, retrieves structured memory/evidence, rejects expired or unsafe records, ranks what matters for the current intent, progressively expands repository evidence only as needed and compiles the result under a hard budget. Persisted symbol snapshots let later sessions distinguish verified current source from historical, contradicted or missing evidence. CI quality gates protect the measured retrieval, token-budget and provenance behavior from silent regressions.

## Main MCP tools

| Tool | Purpose |
|---|---|
| `resume_project` | Return a concise continuation brief |
| `capture_project_memory` | Save decisions, tasks, warnings, files and state together |
| `search_semantic_memory` | Search project memory by meaning with lexical fallback |
| `load_unified_context` | Return optimized project context through the Context Packet delivery path |
| `retrieve_repository_context` | Retrieve bounded repository map/file/symbol/fragment evidence with provenance and token limits |
| `capture_symbol_snapshot` | Persist the current clean Git HEAD symbol snapshot and classified evolution |
| `get_symbol_history` | Return bounded snapshots, changes, links and current verification state for a logical symbol |
| `compare_symbol_commits` | Compare classified symbol changes between two persisted commits |
| `link_symbol_memory` | Link a logical symbol to a validated decision or task in the same owner/project scope |
| `invalidate_symbol_evidence` | Mark symbol evidence stale/contradicted/missing/unverified without deleting history |
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

Persistent Memory MCP uses explicit, fail-closed maintenance and context contracts:

- backups use SQLite's backup API rather than copying a live file;
- successful backups must pass integrity validation;
- manifests include SHA-256 and bounded structural metadata, not stored memory contents;
- health diagnostics are read-only;
- restore uses plan → explicit confirmation → fresh safety backup → atomic replacement → validation → rollback on failure;
- migrations use read-only preview and verified pre-migration backup before explicit apply;
- startup refuses stale existing schemas rather than automigrating;
- deletion/retention uses exact plan fingerprints and short-lived confirmation;
- repository retrieval is local/read-only, root-contained, ignored-path aware and fragment-bounded;
- persistent symbol capture requires a clean HEAD, stores hashes/bounded metadata instead of source bodies and refuses speculative ambiguous rename matches;
- Context Compiler quality gates require full token fit/provenance/safety and explicitly fail on stale/poisoned evidence scenarios;
- context-managed SQLite handles close deterministically after commit/rollback semantics.

## Privacy and product scope

- SQLite is the default local persistence backend.
- The dashboard binds to localhost only.
- Reads/writes are scoped by project and local owner identity.
- Sensitive values are redacted before persistence and recognized secrets are redacted from emitted repository fragments.
- Context compilation, repository retrieval and symbol-history capture do not execute repository code.
- Quality evaluation uses synthetic non-sensitive fixtures and no remote telemetry/provider calls.
- Optional exact token measurement runs locally; the fallback is provider-free.
- Team memberships, shared roles, billing and public collaborative dashboards are out of scope.

## Roadmap

The mandatory post-v0.3 order is:

1. ✅ **Context Packet + model-aware token accounting** — PR #60 / MEM-36 complete.
2. ✅ **Progressive repository retrieval** — PR #62 / MEM-37 complete.
3. ✅ **Persistent code provenance and symbol evolution** — PR #64 / MEM-38 complete; Quality #250 green.
4. 🟡 **Context-quality regression guardrails** — PR #66 / MEM-39 in review with deterministic thresholds and adversarial gates.
5. **Operational project map / Galaxy** built on verified retrieval/provenance/quality data.

See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance criteria, sequencing rules and current evidence.

## Documentation

- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Delivery roadmap](docs/ROADMAP.md)
- [Context Compiler quality evaluation](docs/CONTEXT_QUALITY.md)
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