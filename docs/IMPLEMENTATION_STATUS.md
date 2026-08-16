# Persistent Memory MCP implementation status

Last reconciled for the post-v0.3 Context Compiler phase and PR #64. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

The local data-safety foundation is mature: private SQLite storage, owner/project isolation, WAL-safe backup, SHA-256 manifests, read-only health diagnostics, confirmed restore with rollback, versioned backup-first migrations, explicit upgrade tooling, deterministic SQLite connection lifecycle, validated Settings and cross-platform release-artifact testing.

The first two post-v0.3 Context Compiler milestones are complete: PR #60 established Context Packet v1 with hard serialized token budgets, and PR #62 added progressive map → file → symbol → fragment repository retrieval with bounded cryptographic/Git provenance.

PR #64 implements the third mandatory milestone: **persistent code provenance and symbol evolution**. Local SQLite can now retain commit-scoped symbol snapshots, stable logical identity across moves and conservative renames, classified changes and typed evidence instead of assuming that a parser result remains current forever. History output explicitly distinguishes verified source from stale, contradicted, missing or unverified evidence and shares the Context Packet token-budget contract.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and local onboarding | Complete foundation | `init`, `doctor`, `status`, `health`, `serve` | Ongoing UX refinement |
| SQLite local-first storage | Complete | WAL, foreign keys, versioned migrations | Future numbered migrations as schema evolves |
| Verified backup + manifests | Complete foundation | Backup API, integrity check, SHA-256 sidecars | Optional rotation/signing refinements |
| Health + maintenance readiness | Complete foundation | Read-only checks and verified-backup awareness | Dashboard presentation |
| Confirmed restore | Complete foundation | Two-phase plan/execute, safety backup, rollback | Dashboard integration only |
| Installed upgrade lifecycle | Complete | v0.2.0 → current schema package regression | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context ranking/filtering | Complete foundation | intent-aware selection, expiry/trust filtering, compression | Quality guardrails remain planned |
| Context Packet v1 | **Complete foundation** | PR #60 / Quality #226 | Extend as later evidence types require |
| Model-aware token accounting | **Complete foundation** | deterministic fallback + optional tiktoken reference | Broader benchmark corpus later |
| Progressive repository retrieval | **Complete** | PR #62 / MEM-37 | Ongoing ranking/benchmark refinement |
| Persistent symbol evolution | **Delivery implemented** | Issue #63 / PR #64 / MEM-38 | Exact final-head cross-platform gate + merge |
| Git verification | Complete foundation | repository/branch/commit/file verification | Broader provenance consumers later |
| Code intelligence | **Complete foundation** | Python/TS/JS/SQL extraction + bounded graph + persistent revision history | Richer language parsers/relationships later |
| Automatic continuation | Partial | sessions/checkpoints/handoff | project resolution + automatic milestone capture |
| Hybrid search/embeddings | Complete foundation | semantic + lexical fallback | broader quality/cost benchmarks |
| Evaluation/provenance suite | Complete foundation | agent, token, retrieval and symbol-evolution regressions | context-quality golden scenarios are Step 4 |
| Dashboard/Galaxy | Partial foundation | localhost operational views + bounded graph | operational project map is roadmap Step 5 |
| Teams / remote collaboration | Out of scope | explicit product decision | no implementation planned |

## Context Packet v1 — complete foundation

PR #60 exposes a versioned packet through the real `ContextOptimizer → ModelRouter` delivery path.

The packet includes:

- contract version (`1.0`);
- current objective/intent;
- next safe action when explicitly available;
- compact provenance and verification state;
- hard token budget and final serialized token count;
- tokenizer/model identity and exact-vs-estimated mode;
- selected, dropped, compressed and token-cost metrics per context block.

Compatibility guarantees:

- `build_context()` keeps its historical caller contract;
- 256-token requests remain supported with compact control metadata;
- the active counter measures the complete serialized response after final routing annotations;
- unknown model/tokenizer mappings can fall back locally without a provider network call.

Validated fallback measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Python/source code | 138 | 140 | **1.45%** |

Quality #226 passed the complete Ubuntu/Windows/macOS × Python 3.11–3.13 matrix, reference-tokenizer jobs, release artifacts and dependency audit.

## Progressive repository retrieval — complete

PR #62 exposes `retrieve_repository_context` through the real MCP runtime.

The retrieval service:

1. maps supported repository paths with `git ls-files` without loading every file;
2. ranks a bounded candidate set using path evidence and local bounded `git grep` signals;
3. parses only candidate files with the existing Python/TypeScript/JavaScript/SQL parsers;
4. expands bounded graph neighbors;
5. reads only selected line fragments.

Every fragment carries repository-relative path, line range, content SHA-256, file SHA-256 and Git commit/ref provenance. Traversal/root escape is rejected, configured ignore patterns apply, recognized secrets are redacted, code is never executed, and file/symbol/neighbor/byte/page/token limits are explicit.

Reproducible evaluation:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes | **284 B** |
| Target fragment/file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

## Persistent symbol provenance and evolution — PR #64 / MEM-38

### SQLite model and migration

PR #64 advances local SQLite to schema v2 with four bounded tables:

- `code_symbol_snapshot_runs` — one capture per owner/project/repository/commit;
- `code_symbol_snapshots` — bounded symbol identity/provenance without source bodies;
- `code_symbol_changes` — classified predecessor/current relationships;
- `code_symbol_links` — typed evidence to files, commits, tests and validated project memory.

Migration `0002` uses the existing migration contract: read-only preview, checksum verification, verified pre-migration backup and transactional apply. Fresh databases bootstrap migration history `[1, 2]`. The historical installed v0.2.0 upgrade regression now requires both migrations and proves existing task data survives while the symbol-evolution tables are created.

### Capture and identity

`SymbolEvolutionService.capture()`:

- is scoped by `OWNER_ID + project_id + repository`;
- requires a clean Git HEAD and revalidates it before persistence;
- is idempotent for an already captured commit;
- finds the nearest persisted Git ancestor rather than assuming insertion order;
- persists bounded/redacted signatures and signature/body/file hashes, never source bodies;
- records `added`, `modified`, `moved`, `renamed`, `deleted` and `unchanged` changes.

Logical identity is fail-safe:

- exact qualified identity is preferred;
- exact unique body matches preserve identity across moves;
- stronger name/signature matches are used next;
- a name-only rename may use a normalized bounded signature only when that signature is unique on both old and new sides;
- ambiguous candidates are not merged speculatively.

### Deterministic history and trust state

SQLite `datetime('now')` timestamps can collide within one second. PR #64 therefore uses deterministic `rowid DESC` tie-breaking wherever latest runs/snapshots/changes are selected. This prevents a just-captured current HEAD from being misclassified as stale because an older same-second snapshot happened to sort first.

`get_symbol_history` returns bounded snapshots, classified changes and evidence plus one current state:

- `verified` — current HEAD/file still matches the persisted evidence;
- `stale` — repository state changed relative to the latest evidence;
- `contradicted` — evidence was explicitly invalidated as conflicting;
- `missing_source` — the source/symbol was deleted or unavailable;
- `unverified` — evidence exists without a current verification claim.

Evidence invalidation updates state and reason metadata without deleting history.

### Evidence relationships

Automatic evidence includes:

- `defined_in → file` with file hash;
- `observed_at → commit`;
- `tested_by → test` when the existing code graph proves a test symbol calls the target.

Explicit `decision` and `task` links are permitted only after validating the target belongs to the same owner/project scope. The schema also reserves the typed `deployment` target for future evidence producers rather than inventing unverified deployment links.

### Runtime tools

Local SQLite runtime installs:

- `capture_symbol_snapshot`;
- `get_symbol_history`;
- `compare_symbol_commits`;
- `link_symbol_memory`;
- `invalidate_symbol_evidence`.

### Reproducible evaluation

`scripts/evaluate_symbol_evolution.py` creates a deterministic two-commit repository containing Python, TypeScript, JavaScript and SQL. It captures both commits and fails unless all required checks pass.

First validated Linux output:

| Metric | Result |
|---|---:|
| Languages | **javascript, python, sql, typescript** |
| Initial symbols | **4** |
| Renamed | **1** |
| Moved | **1** |
| Modified | **2** |
| Rename preserves `logical_id` | **true** |
| Renamed symbol current state | **verified** |

The evaluation is part of the reference CI jobs on Ubuntu, Windows and macOS. The normal suite separately covers a three-commit history with movement, modification, rename, deletion, test evidence, decision/task links, explicit contradiction, idempotent recapture and dirty-working-tree stale detection.

## Existing local data-safety contracts

### Backup and manifest

- active SQLite databases are copied with `sqlite3.Connection.backup()`;
- WAL mode is supported;
- same-path/overwrite attempts are rejected;
- completed copies pass integrity validation;
- sidecar manifests provide SHA-256 and bounded structural metadata without memory contents.

### Health

- bounded `quick_check` on every report;
- optional full `integrity_check`;
- foreign-key/index checks;
- DB/WAL/SHM size and free disk reporting;
- latest valid backup awareness;
- no normal output of stored memory values or the absolute active DB path.

### Restore

- read-only plan verifies manifest/checksum/integrity/schema/headroom;
- HMAC confirmation is exact-plan-bound and single-use;
- fresh verified safety backup precedes replacement;
- WAL-aware logical fingerprinting detects meaningful drift;
- atomic replacement and post-validation are mandatory;
- failed validation restores the safety backup automatically.

### Versioned migration

- read-only preview;
- checksum-validated migration history;
- verified pre-migration backup;
- transaction-per-migration execution;
- explicit `memory-mcp-migrate --apply --yes` mutation;
- startup never automigrates an existing stale database;
- historical installed v0.2.0 data-preservation regression runs across supported operating systems.

## Product scope

Persistent Memory MCP is designed around:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- project and local-owner isolation;
- optional self-managed remote storage adapters without changing product direction.

Not planned:

- workspace invitations;
- team memberships or role hierarchies;
- public remote collaborative dashboards;
- billing/organization administration;
- automatic code execution from stored memory or repository retrieval.

## Post-v0.3 completion sequence

1. ✅ **Context Packet + token accounting** — PR #60 / MEM-36 complete.
2. ✅ **Progressive repository retrieval** — PR #62 / MEM-37 complete.
3. ✅ **Persistent code provenance/symbol evolution** — PR #64 / MEM-38 implementation complete; exact-head merge gate pending.
4. ⬜ **Context-quality regression guardrails** — next after PR #64 merges.
5. ⬜ **Operational project map / Galaxy** after the evidence layers above exist.

## Definition of done for PR #64 / MEM-38

- [x] Schema v2 and migration `0002` implemented with packaged assets.
- [x] Fresh schema and installed historical upgrade validate migrations `[1, 2]`.
- [x] Clean-HEAD, project/owner-scoped, idempotent snapshot capture implemented.
- [x] Added/modified/moved/renamed/deleted/unchanged classification implemented.
- [x] Deterministic same-second history ordering implemented.
- [x] Conservative unique rename matching preserves logical identity without speculative merges.
- [x] File/commit/test evidence plus validated decision/task links implemented.
- [x] Explicit evidence invalidation preserves history.
- [x] Symbol history uses shared Context Packet token accounting and a hard budget.
- [x] Reproducible Python/TypeScript/JavaScript/SQL evaluation added to cross-platform CI.
- [x] README, ROADMAP, IMPLEMENTATION_STATUS and Notion synchronized in the branch.
- [ ] Exact final PR head passes the complete Ubuntu/Windows/macOS Quality matrix and release-artifact validation.
- [ ] PR #64 merged.
- [ ] MEM-38 marked complete in Notion.

Step 4 begins only after those final gates close. Its focus is no longer storage or symbol identity: it will measure whether compiled context is actually relevant, provenance-complete, economical and resistant to stale/poisoned evidence.
