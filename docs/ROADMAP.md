# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system and Context Compiler for MCP-compatible development agents**. The v0.3 foundation established recoverable SQLite storage, explicit upgrades and cross-platform packaging. The post-v0.3 sequence adds measurable context delivery, bounded repository evidence, persistent code provenance, quality regression gates and an operational project map.

This document mirrors the canonical roadmap maintained in Notion. Product scope remains one local installation, localhost-only operational UI, project/owner isolation, no shared workspace roles and no automatic repository code execution.

## Status legend

- ✅ **Complete** — implemented, integrated, documented and validated by the required delivery gate.
- 🟡 **In review** — implementation exists but the exact final-head gate/merge is still open.
- ⬜ **Planned** — sequenced work not started yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Local data safety and recovery — ✅ Complete foundation

- private SQLite storage with WAL and foreign keys;
- owner/project isolation and secret redaction;
- WAL-safe backup through SQLite's backup API;
- SHA-256 backup manifests and integrity verification;
- read-only `memory-mcp health` diagnostics;
- two-phase confirmed restore with safety backup and rollback;
- versioned checksum-verified SQLite migrations;
- explicit `memory-mcp-migrate` preview/apply flow;
- fail-closed startup for stale existing schemas;
- deterministic SQLite connection close semantics.

### Package and upgrade safety — ✅ Complete foundation

- SQLite-first core dependencies with optional Supabase/PostgreSQL extras;
- validated immutable RuntimeSettings foundation;
- Ubuntu, Windows and macOS CI across Python 3.11–3.13;
- wheel/sdist build and clean-install validation;
- installed v0.2.0 → current schema migration regression with existing data preserved;
- release-artifact checksums and backup-first rollback documentation.

### Memory, search and development intelligence — ✅ Foundation

- decisions, tasks, warnings, sessions, checkpoints and file memory;
- hybrid semantic + lexical search with local fallback;
- persisted embedding lifecycle;
- Git repository/branch/commit verification;
- Python/TypeScript/JavaScript/SQL symbol extraction;
- bounded code-impact graphs;
- progressive repository map → file → symbol → fragment retrieval;
- persistent symbol snapshots/evolution with typed evidence;
- duplicate/contradiction intelligence;
- deployment history/risk gates;
- localhost dashboard and bounded Galaxy views.

Automatic continuation remains a parallel partial capability; it is not allowed to displace the mandatory Context Compiler sequence.

## Post-v0.3 mandatory sequence

### 1. Versioned Context Packet and real token accounting — ✅ Complete

**Notion:** MEM-36  
**GitHub:** Issue #56 / PR #60  
**Gate:** Quality #226

Delivered:

- stable Context Packet v1 on the real optimizer/model-routing path;
- objective, next safe action, provenance and verification state;
- hard serialized token budget and authoritative final count;
- tokenizer/model identity with deterministic provider-free fallback;
- selected/dropped/compressed/token-cost metrics per block;
- compatibility with historical `build_context()` callers and 256-token requests.

Reference fallback measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Source code | 138 | 140 | **1.45%** |

The guardrail allows ≤40% error on the initial fixtures; the validated worst case is 15.94%.

### 2. Progressive repository retrieval — ✅ Complete

**Notion:** MEM-37  
**GitHub:** Issue #61 / PR #62  
**Gate:** Quality #235

Repository evidence expands in stages instead of loading every source file:

1. compact repository map from `git ls-files`;
2. deterministic candidate-file ranking with path + bounded local `git grep` evidence;
3. symbol extraction only from bounded candidates;
4. bounded graph-neighbor expansion;
5. exact selected line fragments.

Safety/contract guarantees:

- traversal/root-escape rejection;
- configured ignore patterns plus code-intelligence excludes;
- deterministic score ordering and bounded cursor pagination;
- cursor fingerprints bound to query, Git commit and candidate-file hashes;
- SHA-256 + Git commit/ref provenance per fragment;
- secret redaction before fragment emission;
- explicit file/symbol/neighbor/byte/page/token limits;
- shared Context Packet token-counter contract;
- repository code is never executed.

Reference evaluation:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes | **284 B** |
| Target fragment/file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

### 3. Persistent code provenance and symbol evolution — ✅ Complete

**Notion:** MEM-38  
**GitHub:** Issue #63 / PR #64  
**Gate:** Quality #250

Delivered:

- SQLite schema v2 with symbol snapshot runs, snapshots, classified changes and typed evidence links;
- migration `0002` through preview → verified backup → transactional apply;
- clean-HEAD, owner/project/repository-scoped idempotent capture;
- bounded/redacted signatures and hashes without source bodies;
- nearest persisted Git ancestor comparison;
- `added`, `modified`, `moved`, `renamed`, `deleted`, `unchanged` classification;
- stable logical identity across moves and conservative unique rename matches;
- deterministic same-second tie-breaking;
- file/commit/test evidence and validated decision/task links;
- explicit `verified`, `stale`, `contradicted`, `missing_source`, `unverified` evidence states;
- bounded symbol-history queries using the shared token-counter contract.

The reproducible evaluation covers Python, TypeScript, JavaScript and SQL and validated **1 renamed, 1 moved and 2 modified** symbols while preserving rename identity.

### 4. Context quality and regression guardrails — ✅ Complete

**Notion:** MEM-39  
**GitHub:** Issue #65 / PR #66  
**Gate:** Quality #262

Delivered:

- versioned non-sensitive local coding-task corpus;
- explicit versioned thresholds;
- deterministic evaluator over the real progressive retrieval path;
- file/symbol recall and precision, hard token fit, token savings, provenance coverage and latency metrics;
- fixture/evaluator/threshold/tokenizer/model identity;
- unit tests proving deliberate metric degradation fails closed;
- adversarial cases for expired/untrusted memory, prompt injection, dirty cursors, rename continuity, contradicted evidence and dirty-Git stale evidence;
- Ubuntu/Windows/macOS quality + adversarial gates.

Initial v1 baseline:

| Metric | Baseline | Gate |
|---|---:|---:|
| File recall@5 | **1.000** | ≥ **1.000** |
| File precision@5 | **0.200** | ≥ **0.200** |
| Symbol recall@8 | **1.000** | ≥ **1.000** |
| Symbol precision@8 | **0.125** | ≥ **0.125** |
| Token-fit rate | **1.000** | ≥ **1.000** |
| Token savings | **0.7722** | ≥ **0.400** |
| Provenance coverage | **1.000** | ≥ **1.000** |
| Safety pass rate | **1.000** | ≥ **1.000** |

The precision floors protect the current baseline; they are not claims of optimal ranking.

### 5. Operational project map / risk-oriented Galaxy — 🟡 In review

**Notion:** MEM-40  
**GitHub:** Issue #67 / PR #68

PR #68 converts the existing bounded Galaxy into an operational projection **without adding another repository scanner or graph database**.

#### Operational read model

`OperationalMapService` composes existing SQLite and persistent `code_symbol_*` evidence into bounded, deterministic views:

- global owner-scoped project overview;
- per-project impact graph;
- project → repository → file → symbol relationships;
- verified symbol links to tasks, decisions, files/tests/deployments where present;
- project-level warnings/tasks/decisions;
- risk and persisted verification state;
- current-change affected-area projection based only on latest persisted repository snapshot runs.

The map is read-only and emits compact metadata. It does not return full source bodies, decision/task details, session/checkpoint bodies or absolute repository roots. Short labels pass through existing secret redaction.

#### Owner isolation and HTTP surface

Operational owner resolution fails closed:

1. use configured `--owner-id` / `OWNER_ID` when present;
2. otherwise infer only when exactly one project owner exists;
3. reject no-owner or ambiguous multi-owner databases instead of mixing data.

New localhost-only endpoints:

```text
GET /api/operational/projects
GET /api/operational/graph?project_id=<id>
GET /api/operational/export.json?project_id=<id>
GET /galaxy/operational?project_id=<id>
```

Supported filters include `verification`, `risk` and project-scoped `changed_only`. Existing Dashboard/Galaxy endpoints remain compatible.

#### Risk-oriented Galaxy

Operational mode adds:

- risk filter;
- verification-state filter;
- changed-only filter;
- visible critical/high/medium, stale and contradicted states;
- changed/missing/risk/verification summary counts;
- separate operational SVG/PNG export names;
- existing keyboard/ARIA, drag, zoom, focus and minimap behavior.

#### Bounds and performance gate

`scripts/evaluate_operational_map.py` is part of the cross-platform reference CI jobs. Fixture:

- 20 active-owner projects plus one foreign-owner project;
- 120 symbols across 12 files;
- 20 tasks;
- 24 currently changed symbols concentrated in a bounded affected area.

CI limits: max 20 projects, 180 nodes, 400 edges, 50 records per kind; latency ceiling is a deliberately non-flaky **5,000 ms** for overview/full/changed graph.

Validated structural output is identical across reference platforms:

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

These are regression-fixture observations, not production SLA claims. The gate also requires owner isolation, bounds, read-only output, secret redaction, no absolute repository root, no full body fields and a genuinely reduced `changed_only` graph.

Remaining before MEM-40 is complete:

- [x] owner-scoped bounded operational read model;
- [x] current-change / risk / verification semantics;
- [x] cross-owner isolation and fail-closed owner resolution;
- [x] localhost-only operational HTTP endpoints and bounded export;
- [x] risk-oriented operational Galaxy with legacy compatibility;
- [x] HTTP/security/UI/read-model regression tests;
- [x] reproducible cross-platform bounds/latency gate;
- [x] public operational-map documentation;
- [ ] README, IMPLEMENTATION_STATUS, `llms.txt` and Notion fully reconciled;
- [ ] exact final PR #68 HEAD passes complete Quality after documentation sync;
- [ ] PR #68 merged and MEM-40 marked complete.

See [OPERATIONAL_MAP.md](OPERATIONAL_MAP.md) for the detailed public contract.

## Parallel non-blocking work

These items may receive maintenance fixes after the mandatory phase but should not silently redefine it:

- automatic project resolution and continuation capture;
- broader embedding/search benchmarks;
- provider-specific configuration cleanup;
- optional Supabase/PostgreSQL adapter maintenance;
- further Dashboard pagination/UX refinements.

## Product scope decision — 🚫 No collaborative SaaS

Persistent Memory MCP remains:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- isolated by project and local owner identity;
- compatible with local MCP clients.

Workspace invitations, shared memberships, team-role hierarchies, billing and a public remote collaborative dashboard are not milestones.

## Definition of done for each roadmap step

A step is incomplete until all are true:

1. the code path is integrated into the real product rather than only exposed as a helper;
2. deterministic tests cover success, failure and boundary behavior;
3. the relevant Ubuntu/Windows/macOS CI gate passes;
4. measurable evidence is recorded for quality/cost/performance claims;
5. README, ROADMAP, IMPLEMENTATION_STATUS, public docs and Notion agree;
6. the implementation does not broaden local-first scope or silently execute destructive/code actions.

## Current recommended order

1. Finish documentation synchronization for **PR #68 / MEM-40**.
2. Freeze the exact final PR #68 HEAD and require the complete Quality matrix.
3. If green, merge PR #68 and mark MEM-40 complete.
4. Re-evaluate the post-v0.3 phase definition of done before starting any new numbered milestone; do not invent a new phase without an explicit roadmap decision.
