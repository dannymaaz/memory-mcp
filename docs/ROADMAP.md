# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system for MCP-compatible development agents**. The v0.3 foundation established recoverable SQLite storage, explicit upgrades and cross-platform packaging. The active roadmap now focuses on turning stored memory into a **measurable Context Compiler** that can deliver only the context required for the next safe action.

This document mirrors the canonical post-v0.3 roadmap maintained in Notion. Product scope remains one local installation, localhost-only operational UI, project/owner isolation, no shared workspace roles and no automatic code execution.

## Status legend

- ✅ **Complete** — implemented, integrated and required repository regression evidence is part of the delivery gate.
- 🟡 **In review / partial** — implementation exists but the end-to-end gate is not fully closed.
- ⬜ **Planned** — sequenced work not started yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Local data safety and recovery — ✅ Complete foundation

- private SQLite storage with WAL and foreign keys;
- owner/project isolation and secret redaction;
- WAL-safe backups using SQLite's backup API;
- SHA-256 backup manifests and integrity verification;
- read-only `memory-mcp health` diagnostics;
- two-phase confirmed restore with a verified safety backup and rollback;
- versioned checksum-verified SQLite migrations;
- explicit `memory-mcp-migrate` preview/apply flow;
- fail-closed startup when an existing database needs migration;
- deterministic close semantics for context-managed SQLite connections.

### Package and upgrade safety — ✅ Complete foundation

- SQLite-first core dependencies with optional Supabase/PostgreSQL extras;
- validated immutable RuntimeSettings foundation;
- Ubuntu, Windows and macOS CI across Python 3.11–3.13;
- wheel/sdist build and clean-install validation;
- real installed v0.2.0 → current schema migration regression with existing data preserved;
- release-artifact checksums and backup-first rollback documentation.

### Memory, search and development intelligence — ✅/🟡 Foundation

Complete foundations:

- decisions, tasks, warnings, sessions, checkpoints and file memory;
- hybrid semantic + lexical search;
- persisted embedding lifecycle and local fallback;
- Git repository/branch/commit verification;
- code symbol extraction and bounded impact graphs;
- progressive repository map → file → symbol → fragment retrieval;
- persistent symbol snapshots/evolution with typed evidence;
- duplicate/contradiction intelligence;
- deployment history, risk gates and evaluation regressions;
- localhost dashboard and bounded Galaxy knowledge view.

Known partial areas that the remaining roadmap addresses:

- automatic continuation checkpoints remain partial;
- context-quality golden scenarios still need explicit cost/relevance guardrails;
- Galaxy still needs an operational projection rather than being only a knowledge visualization.

## Post-v0.3 mandatory sequence

The following order is intentional. A later step should not bypass an earlier contract because every layer depends on the evidence and budget semantics established before it.

### 1. Versioned Context Packet and real token accounting — ✅ Complete

**Notion:** MEM-36  
**GitHub:** Issue #56 / PR #60

Delivered:

- stable `Context Packet` v1 through the real optimizer/model-routing path;
- packet version, objective, next safe action when available, provenance and verification state;
- hard serialized token budget and authoritative final count;
- tokenizer/model identity with deterministic provider-free fallback;
- selected/dropped/compressed/token-cost metrics per context block;
- compatibility with existing `build_context()` callers and 256-token requests.

Validated by Quality #226 across Ubuntu/Windows/macOS and Python 3.11–3.13. Reference measurements against `gpt-4o` / `tiktoken:o200k_base`:

- Spanish fixture: 69 reference vs 80 fallback — **15.94% error**;
- source-code fixture: 138 reference vs 140 fallback — **1.45% error**;
- guardrail: worst fixture error ≤40%; validated worst case **15.94%**.

### 2. Progressive repository retrieval — ✅ Complete

**Notion:** MEM-37  
**GitHub:** Issue #61 / PR #62

The implementation expands repository evidence in stages instead of reading/indexing every file content up front:

1. compact repository/directory map from `git ls-files`;
2. deterministic relevant-file ranking using path evidence and bounded local `git grep` signals;
3. symbol extraction only from bounded candidate files using the existing Python/TypeScript/JavaScript/SQL parsers;
4. bounded graph-neighbor expansion;
5. exact line fragments only for selected symbols.

Safety and contract properties:

- normalized repository-relative paths with traversal/root-escape rejection;
- `RuntimeSettings.ignore_patterns` plus existing code-intelligence excludes;
- stable score ordering and bounded cursor pagination;
- cursor fingerprints include query, Git commit and candidate-file hashes, so relevant dirty working-tree changes invalidate stale cursors;
- fragment provenance includes path, start/end lines, fragment SHA-256, file SHA-256 and commit/ref;
- recognized secrets are redacted before fragment emission;
- explicit caps for map files, parsed files, symbols, graph neighbors, file bytes, total bytes, fragment lines, page size and tokens;
- final serialized retrieval uses the Context Packet token-counter contract rather than a separate estimator;
- repository code is never executed.

Reproducible PR #62 evaluation (`scripts/evaluate_repository_retrieval.py`):

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes | **284 B** |
| Target file lines | **125** |
| Target fragment lines | **7** |
| Fragment/file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

Additional regressions verify symbol-only discovery, stale cursors after committed and uncommitted candidate changes, secret redaction, Python/TS/JS/SQL symbols, path traversal, ignored paths and byte/token limits.

### 3. Code provenance and symbol evolution — ✅ Delivery implemented

**Notion:** MEM-38  
**GitHub:** Issue #63 / PR #64

PR #64 persists code evolution instead of treating parser output as timeless current truth.

Delivered contract:

- SQLite schema v2 with snapshot runs, per-symbol snapshots, classified changes and typed evidence links;
- migration `0002` through the existing preview → verified backup → transactional apply lifecycle;
- fresh databases bootstrap migration history `[1, 2]`; historical v0.2 installs upgrade through both versions while preserving existing data;
- capture is scoped by owner + project + repository and accepts only a clean Git HEAD;
- one idempotent run per owner/project/repository/commit;
- bounded/redacted signatures and SHA-256 hashes are persisted without source bodies;
- nearest persisted Git ancestor is used as the comparison baseline;
- changes are classified as `added`, `modified`, `moved`, `renamed`, `deleted` or `unchanged`;
- stable `logical_id` survives exact moves and conservative unique rename matches;
- rename matching prefers exact identity/body evidence and only falls back to a normalized bounded signature when the candidate is unique on both sides;
- deterministic `rowid` tie-breaking prevents same-second SQLite timestamps from selecting stale snapshots;
- file/commit/test evidence is added automatically where available;
- decision/task evidence requires explicit owner/project validation;
- evidence can be marked `stale`, `contradicted`, `missing_source` or `unverified` without deleting history;
- symbol history uses the shared Context Packet token-counter/budget contract;
- the runtime exposes `capture_symbol_snapshot`, `get_symbol_history`, `compare_symbol_commits`, `link_symbol_memory` and `invalidate_symbol_evidence` for local SQLite installations.

Reproducible regression (`scripts/evaluate_symbol_evolution.py`) creates a multi-language two-commit repository and requires:

| Check | Gate |
|---|---:|
| Languages | Python + TypeScript + JavaScript + SQL |
| Rename preserves logical ID | **true** |
| Renamed | **≥ 1** |
| Moved | **≥ 1** |
| Modified | **≥ 1** |
| Current renamed symbol state | **verified** |

The first validated CI execution produced **1 renamed, 1 moved and 2 modified** symbols and preserved the renamed Python symbol identity. The evaluation is wired into the Ubuntu/Windows/macOS reference jobs; exact final PR HEAD must pass those jobs plus the Python 3.11–3.13 matrix and release-artifact upgrade validation before merge.

Exit criteria for PR #64:

- [x] versioned SQLite schema/migration and packaged assets implemented;
- [x] clean-HEAD idempotent snapshot capture implemented;
- [x] added/modified/moved/renamed/deleted classification implemented;
- [x] deterministic history ordering and conservative rename identity implemented;
- [x] typed file/commit/test/decision/task evidence with explicit invalidation implemented;
- [x] hard-budget history output implemented;
- [x] reproducible Python/TS/JS/SQL symbol-evolution evaluation added to cross-platform CI;
- [x] README, ROADMAP, IMPLEMENTATION_STATUS and Notion synchronized in the branch;
- [ ] exact final PR head passes the complete Quality matrix and release-artifact validation;
- [ ] PR #64 merged and MEM-38 marked complete.

### 4. Context quality and regression guardrails — ⬜ Planned

Starts after Step 3 is merged.

- define golden continuation scenarios;
- measure relevance, provenance coverage and unnecessary-context rate;
- compare token cost against task completion quality;
- test poisoned/untrusted memory and stale code evidence;
- make quality regressions visible in CI before context behavior ships.

### 5. Operational project map / Galaxy — ⬜ Planned

Galaxy becomes an operational projection only after Context Packet, retrieval and code provenance are measurable.

Planned views:

- active work and next safe actions;
- stale/contradicted/unverified memories;
- repository hotspots and symbol relationships;
- token-cost and retrieval diagnostics;
- backup/health state and maintenance readiness;
- bounded drill-down without exposing the dashboard remotely.

## Parallel non-blocking work

These items may receive maintenance fixes but must not displace the mandatory sequence above:

- dashboard pagination and accessible empty/loading/error states;
- automatic project resolution and continuation capture;
- provider-specific configuration cleanup;
- broader embedding/search benchmarks;
- optional Supabase/PostgreSQL adapter maintenance.

## Product scope decision — 🚫 No collaborative SaaS

Persistent Memory MCP remains:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- isolated by project and local owner identity;
- compatible with local MCP clients.

Workspace invitations, shared memberships, team-role hierarchies, billing and a public remote collaborative dashboard are not milestones.

## Definition of done for each roadmap step

A step is not complete until all of the following are true:

1. the code path is integrated into the real product rather than only exposed as a helper;
2. deterministic tests cover success, failure and boundary behavior;
3. the relevant Ubuntu/Windows/macOS CI gate passes;
4. measurable evidence is recorded when the step introduces a quality or cost claim;
5. README, this ROADMAP, IMPLEMENTATION_STATUS and the corresponding Notion task agree;
6. the implementation does not broaden local-first scope or silently execute destructive/code actions.

## Current recommended order

1. Finish the exact-head gate and merge **PR #64 — persistent code provenance/symbol evolution**.
2. Start **context quality regression guardrails** with measurable golden scenarios.
3. Evolve **Galaxy into an operational project map** using the verified data from the previous layers.
