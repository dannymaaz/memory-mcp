# Persistent Memory MCP implementation status

Last reconciled for the post-v0.3 Context Compiler phase and PR #68. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The local data-safety foundation is mature: private SQLite storage, owner/project isolation, WAL-safe backups, SHA-256 manifests, read-only health diagnostics, confirmed restore with rollback, versioned backup-first migrations, explicit upgrade tooling, deterministic SQLite connection lifecycle, validated Settings and cross-platform release-artifact testing.

The first four mandatory post-v0.3 Context Compiler milestones are complete:

1. PR #60 / MEM-36 — Context Packet v1 and measurable token accounting;
2. PR #62 / MEM-37 — progressive repository map → file → symbol → fragment retrieval;
3. PR #64 / MEM-38 — persistent commit-scoped symbol provenance/evolution;
4. PR #66 / MEM-39 — deterministic context-quality and adversarial provenance regression gates.

PR #68 / MEM-40 is the active fifth milestone: **bounded operational project map and risk-oriented Galaxy**. The implementation composes the existing persisted project/Git/symbol evidence into owner-scoped read-only summaries and project impact graphs, exposes them through localhost-only endpoints, adds operational risk/verification filters to Galaxy, and gates graph size, isolation, redaction and performance in cross-platform CI.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and local onboarding | Complete foundation | `init`, `doctor`, `status`, `health`, `serve` | Ongoing UX refinement |
| SQLite local-first storage | Complete | WAL, foreign keys, versioned migrations | Future numbered migrations as schema evolves |
| Verified backup + manifests | Complete foundation | backup API, integrity check, SHA-256 sidecars | Optional rotation/signing refinements |
| Health + maintenance readiness | Complete foundation | read-only checks and verified-backup awareness | Additional UI presentation only |
| Confirmed restore | Complete foundation | two-phase plan/execute, safety backup, rollback | Additional UI integration only |
| Installed upgrade lifecycle | Complete | v0.2.0 → current schema package regression | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context Packet v1 | Complete | PR #60 / Quality #226 | Extend only when later evidence types require it |
| Progressive repository retrieval | Complete | PR #62 / Quality #235 | Ranking improvements must stay behind quality gates |
| Persistent symbol evolution | Complete | PR #64 / Quality #250 | Richer language relationships later |
| Context quality regression gates | Complete | PR #66 / Quality #262 | Thresholds may tighten with better ranking |
| Operational map read model | **In review** | PR #68 / MEM-40 | Exact final-head gate + merge |
| Risk-oriented operational Galaxy | **In review** | PR #68 / MEM-40 | Exact final-head gate + merge |
| Automatic continuation | Partial | sessions/checkpoints/handoff | Project resolution + automatic milestone capture |
| Hybrid search/embeddings | Complete foundation | semantic + lexical fallback | Broader quality/cost benchmarks |
| Teams / remote collaboration | Out of scope | explicit product decision | No implementation planned |

## Context Compiler milestones 1–4 — complete

### Context Packet v1

PR #60 established:

- versioned packet contract;
- objective and next-safe-action metadata;
- compact provenance/verification state;
- hard final serialized token budget;
- tokenizer/model identity;
- selected/dropped/compressed/token-cost metrics.

Quality #226 passed Ubuntu/Windows/macOS and Python 3.11–3.13.

### Progressive repository retrieval

PR #62 established bounded local retrieval:

1. repository map;
2. candidate files;
3. symbols only from bounded candidates;
4. bounded graph neighbors;
5. exact source fragments.

Reference evaluation maps 80 supported files, parses 6 candidates (**7.5%**), returns 2 fragments / 284 bytes and fits **1,305 / 1,400** tokens.

### Persistent symbol provenance/evolution

PR #64 advanced SQLite to schema v2 with snapshot runs, snapshots, changes and typed evidence links. Capture requires clean Git HEAD and is owner/project/repository scoped. Evidence can be `verified`, `stale`, `contradicted`, `missing_source` or `unverified` without deleting history.

The reproducible evaluation covers Python, TypeScript, JavaScript and SQL and validated **1 renamed, 1 moved and 2 modified** symbols with logical rename identity preserved. Quality #250 passed the exact final HEAD.

### Context-quality regression guardrails

PR #66 / MEM-39 adds the versioned local golden corpus, explicit thresholds and adversarial gates. Initial v1 baseline:

| Metric | Baseline | Gate |
|---|---:|---:|
| File recall@5 | **1.000** | ≥1.000 |
| File precision@5 | **0.200** | ≥0.200 |
| Symbol recall@8 | **1.000** | ≥1.000 |
| Symbol precision@8 | **0.125** | ≥0.125 |
| Token-fit rate | **1.000** | ≥1.000 |
| Token savings | **0.7722** | ≥0.400 |
| Provenance coverage | **1.000** | ≥1.000 |
| Safety pass rate | **1.000** | ≥1.000 |

Adversarial gates cover expired/untrusted memory, prompt injection, dirty cursor invalidation, rename identity continuity, contradicted evidence and dirty-Git stale evidence. Quality #262 passed the exact final HEAD and PR #66 is merged.

## Operational project map / Galaxy — PR #68 / MEM-40

### Read model

`persistent_memory_mcp.operational_map.OperationalMapService` provides two compact read-only projections:

- `project_overview()` — bounded owner-scoped project list with active/blocked work, warnings, changed-symbol count, evidence state and risk;
- `impact_graph(project_id)` — bounded project → repository → file → symbol → task/decision/evidence graph.

The service consumes existing SQLite and `code_symbol_*` evidence. It does not rescan or execute repository code.

### Current-change semantics

`changed_only=true` is based only on the **latest persisted snapshot run for each repository**. The affected-area graph starts from changed files/symbols, keeps directly linked operational evidence and adds only the ancestor hierarchy needed to understand the change. It does not fan out from the project node into unrelated tasks.

### Verification and risk

Persisted verification states:

- `verified`
- `stale`
- `contradicted`
- `missing_source`
- `unverified`

Operational risk projection:

- `critical`
- `high`
- `medium`
- `low`
- `none`

Contradicted evidence is critical; stale/missing-source evidence is high; unverified evidence is medium. Blocked tasks and active high/critical warnings raise operational risk.

### Payload/privacy contract

Operational payloads are bounded and body-free. They omit full:

- source bodies/signatures;
- task/decision details;
- warning/session/checkpoint bodies;
- absolute repository roots.

Short display labels are bounded and pass through the existing secret redaction function. Cross-owner project access fails closed.

Hard `OperationalMapLimits` maxima:

| Limit | Default | Maximum |
|---|---:|---:|
| Projects | 50 | 100 |
| Repositories | 12 | 20 |
| Nodes | 250 | 500 |
| Edges | 750 | 1,500 |
| Records per kind | 50 | 200 |

### Owner-scoped localhost HTTP surface

Owner resolution:

1. configured `--owner-id` / `OWNER_ID` wins;
2. otherwise infer only if exactly one project owner exists;
3. zero or multiple owners fail closed instead of mixing data.

New endpoints:

```text
GET /api/operational/projects
GET /api/operational/graph?project_id=<id>
GET /api/operational/export.json?project_id=<id>
GET /galaxy/operational?project_id=<id>
```

Filters include `verification`, `risk` and project-scoped `changed_only`. Existing legacy Dashboard/Galaxy endpoints remain compatible. The server remains loopback-only and read-only with no-store, `nosniff`, frame-deny and CSP headers.

### Risk-oriented Galaxy

Operational mode adds:

- risk filter;
- verification filter;
- changed-only filter;
- visible critical/high/medium, stale and contradicted states;
- changed/missing/risk/verification summary counts;
- separate operational SVG/PNG exports;
- the existing drag, zoom, focus, minimap and ARIA/keyboard interactions.

The same renderer detects legacy knowledge graphs and hides operational controls for compatibility.

### Performance and bounds regression

`scripts/evaluate_operational_map.py` builds a deterministic local fixture:

- 20 active-owner projects plus a foreign-owner project;
- 120 symbols;
- 12 files;
- 20 tasks;
- 24 currently changed symbols concentrated in a bounded affected area.

CI fixture limits: 20 projects, 180 nodes, 400 edges, 50 records per kind. Latency guardrail: **≤5,000 ms** for overview/full/changed graphs to avoid hosted-runner flakiness while still catching pathological growth.

Validated structure:

| Metric | Result |
|---|---:|
| Overview projects | **20** |
| Full graph nodes | **154** |
| Full graph edges | **173** |
| Changed-area nodes | **55** |
| Changed-area edges | **74** |

Reference observations:

| Platform | Overview | Full graph | Changed-area graph |
|---|---:|---:|---:|
| Ubuntu | **3.04 ms** | **6.26 ms** | **4.35 ms** |
| Windows | **4.99 ms** | **8.08 ms** | **5.36 ms** |
| macOS | **5.65 ms** | **8.56 ms** | **4.15 ms** |

These are regression-fixture observations, not an SLA. Every reference job also asserts owner isolation, bounds, read-only output, secret redaction, no absolute repo-root leakage, no full body fields and actual changed-area graph reduction.

See [OPERATIONAL_MAP.md](OPERATIONAL_MAP.md) for the public contract.

## Local data-safety contracts

### Backup/manifest

- live SQLite backups use SQLite's backup API;
- completed backups pass integrity validation;
- sidecar manifests carry SHA-256 and bounded structural metadata, not memory contents.

### Health

- read-only `quick_check` plus optional full integrity check;
- foreign-key/index checks;
- DB/WAL/SHM size and free-disk reporting;
- latest verified-backup awareness.

### Restore

- read-only plan;
- exact-plan-bound short-lived confirmation;
- fresh verified safety backup;
- atomic replacement;
- post-validation and automatic rollback on failure.

### Migration

- read-only preview;
- migration checksum history;
- verified pre-migration backup;
- transaction per migration;
- explicit apply;
- no silent startup automigration;
- installed historical-upgrade regression across supported operating systems.

## Product scope

Persistent Memory MCP is designed around:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- project/local-owner isolation;
- optional self-managed remote storage adapters without changing the core product direction.

Not planned:

- workspace invitations;
- team memberships/role hierarchies;
- public collaborative dashboards;
- billing/organization administration;
- automatic code execution from stored memory or repository retrieval.

## Post-v0.3 completion sequence

1. ✅ Context Packet + token accounting — PR #60 / MEM-36.
2. ✅ Progressive repository retrieval — PR #62 / MEM-37.
3. ✅ Persistent code provenance/symbol evolution — PR #64 / MEM-38.
4. ✅ Context-quality regression guardrails — PR #66 / MEM-39 / Quality #262.
5. 🟡 Operational project map / risk-oriented Galaxy — PR #68 / MEM-40 in review.

## Definition of done for PR #68 / MEM-40

- [x] owner-scoped bounded read model;
- [x] current-change affected-area semantics;
- [x] explicit risk and verification states;
- [x] compact body-free/redacted payload contract;
- [x] cross-owner isolation/fail-closed owner resolution;
- [x] localhost-only operational endpoints and bounded JSON export;
- [x] risk-oriented Galaxy with legacy compatibility;
- [x] HTTP/security/UI/read-model tests;
- [x] cross-platform bounds/latency evaluator wired to CI;
- [x] public `OPERATIONAL_MAP.md` contract;
- [ ] README, ROADMAP, IMPLEMENTATION_STATUS, `llms.txt` and Notion fully synchronized;
- [ ] exact final PR #68 HEAD passes complete Ubuntu/Windows/macOS Quality and artifact validation;
- [ ] PR #68 merged and MEM-40 marked complete.

After MEM-40 closes, the current five-step post-v0.3 phase should be re-evaluated against its definition of done before any new numbered milestone is invented.
