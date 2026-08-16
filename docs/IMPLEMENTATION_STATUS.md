# Persistent Memory MCP implementation status

Last reconciled after PR #80 / MEM-29 merged with Quality #346. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The v0.3 technical foundation and the complete five-step Context Compiler phase are delivered. Post-phase reliability work now also includes automatic continuation, deterministic keyset pagination, Dashboard maintenance/UX and an explicit Application composition root with idempotent MCP Tool Registry.

The principal unfinished work is no longer application architecture. It is **release/distribution reconciliation**: v0.3.0 is prepared and validated, but the repository currently has no `v0.3.0` tag or GitHub Release, and `main` has no PyPI Trusted Publishing workflow. External PyPI account configuration becomes the blocker only after the repository-side tag/release/publication path is prepared.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| SQLite local-first storage | Complete foundation | WAL, foreign keys, schema v2, backup-first migrations | Future numbered migrations as schema evolves |
| Backup / manifest / health / restore | Complete foundation | PR #29/#35/#39/#43 | Optional rotation/signing refinements |
| Installed upgrade lifecycle | Complete | real v0.2.0 → v0.3/current package regressions | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context Packet + token accounting | Complete | PR #60 / Quality #226 | Extend only as evidence contracts evolve |
| Progressive repository retrieval | Complete | PR #62 / Quality #235 | Ranking changes remain behind quality gates |
| Persistent symbol provenance/evolution | Complete | PR #64 / Quality #250 | Richer language relationships later |
| Context quality/adversarial gates | Complete | PR #66 / Quality #262 | Thresholds can tighten, not silently regress |
| Operational project map / Galaxy | Complete | PR #68 / Quality #282 | Additional UX refinement only |
| Automatic Continuation Contract | Complete | PR #71 / Quality #290 | Future fields only when justified |
| Deterministic keyset pagination | Complete | PR #73 / MEM-30 / Quality #306 | Optional remote-adapter parity if later required |
| Hybrid search / embeddings | Complete foundation | semantic + lexical local fallback | Broader quality/cost benchmark corpus |
| Dashboard maintenance/UX | Complete | PR #77 / Issue #76 / MEM-12 / Quality #338 | Future optional UX polish only |
| Application container / Tool Registry | **Complete** | PR #80 / Issue #75 / MEM-29 / Quality #346 | Migrate additional integrations only when evidence justifies it |
| v0.3.0 GitHub tag/release | **In review** | PR #54 merged; release commit `4dc160c…`; tag workflow present | Create exact tag, pass artifact workflow, create GitHub Release |
| PyPI publication | **In review → external dependency** | `docs/RELEASING.md`; Issue #53 | Add publication workflow, then configure Trusted Publisher and publish exact release artifacts |
| MCP Registry publication | Pending after PyPI | MEM-33 / Issue #53 | Stable public package/release URLs first |
| Teams / public collaboration | Out of scope | explicit product decision | no implementation planned |

## Completed Context Compiler phase

1. ✅ **Context Packet + model-aware token accounting** — PR #60 / Quality #226.
2. ✅ **Progressive repository retrieval** — PR #62 / Quality #235.
3. ✅ **Persistent code provenance and symbol evolution** — PR #64 / Quality #250.
4. ✅ **Context-quality regression guardrails** — PR #66 / Quality #262.
5. ✅ **Operational project map / risk-oriented Galaxy** — PR #68 / Quality #282.

The phase tracker is closed. No sixth numbered phase item is implied by this document.

## Post-phase reliability

### Automatic Continuation Contract — complete

PR #71 / MEM-31 completed the lifecycle gap that remained after the original session foundation. Continuation Contract v1 stores a bounded/redacted checkpoint containing objective, completed/pending work, blockers, relevant files, validation, next safe action and credential-free Git identity. Repository-bound project resolution fails closed on ambiguous strongest matches, and explicit close, handoff and idle expiry share the same continuation path.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination — complete

PR #73 / MEM-30 adds bounded SQLite keyset paging while preserving historical `select()` compatibility. The contract provides a default page size of 50, hard maximum 200, opaque versioned cursors, query fingerprints, deterministic timestamp + `id` boundaries, first-page snapshot anchoring, validated filter/order identifiers and fail-closed malformed/cross-query cursors.

It is integrated into MCP history reads and localhost Dashboard drill-down. The cross-platform reference evaluator exercises 10,000 owner/project records plus foreign-owner noise and a post-page-1 insert to prove exact traversal without duplicate/skip/scope leakage.

See [PAGINATION.md](PAGINATION.md).

### Dashboard maintenance/UX — complete

PR #77 / MEM-12 completed the genuine Dashboard operations subset while keeping the interface localhost-only. It reuses `HealthService`, backup/restore/retention primitives and signed confirmations rather than introducing raw mutation paths.

Delivered health/storage/backup/verification/sensitivity status; explicit UI states; safe server-generated backup paths; signed restore preview/confirm with safety backup/rollback; signed selective deletion preview/confirm; shared consumed confirmation state between MCP and Dashboard; JSON/header/request-size protections and restrictive same-origin CSP.

Quality #338 passed before merge `43790fdfe9c003a9347496a34b0360d17c95320b`.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application composition + Tool Registry — complete

PR #80 / MEM-29 introduces the explicit architecture boundary without a flag-day server rewrite.

`create_application(settings)` now owns the real runtime composition path. `Application` carries immutable settings, the active server module and the shared registry. Repeated construction with the same settings returns the existing composed application; attempting to recompose the process with incompatible settings fails explicitly.

`ToolRegistry` centralizes dynamic MCP registration/replacement and synchronizes known FastMCP surfaces, module handlers and local tool schemas. Registration is idempotent by tool name; replacing an existing tool does not append duplicate schema entries. A new required tool uses FastMCP's public `tool(...)` API and registration failures raise clearly instead of being silently ignored.

Confirmed Deletion and Verified Restore/Maintenance are the first integrations migrated away from duplicated private registry mutation helpers. Public tool names, signatures, payloads, storage contracts and destructive confirmation behavior remain compatible.

The initialization order is documented and regression-tested, including the requirement that Continuation wrap session close before Session Lifecycle captures it.

Quality #346 passed the full Ubuntu/Windows/macOS × Python 3.11–3.13 matrix plus reference token accounting, release-artifact/upgrade checks and dependency audit before squash merge `f85b4d691ce1716b20ad7a49a02ca62227d03614`.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

## Local data-safety contracts

- **backup:** live SQLite uses SQLite's backup API and verifies integrity;
- **manifest:** SHA-256 sidecars contain bounded structural metadata, not memory contents;
- **health:** read-only integrity/foreign-key/index/disk checks;
- **restore:** preview → exact confirmation → fresh verified safety backup → atomic replacement → post-validation/rollback;
- **migration:** preview → checksum verification → verified backup → transactional explicit apply;
- **deletion:** exact scoped plan + short-lived single-use confirmation;
- **Dashboard maintenance:** localhost-only adapter that reuses backup/restore/delete services rather than raw SQL;
- **context/repository:** bounded, provenance-aware and non-executing by default.

## v0.3.0 distribution state

Release preparation PR #54 is merged. Its validated release merge commit is `4dc160c1fdf0e2858337239c42c9085fe8097493`, and that commit reports package version `0.3.0` and contains the tag-triggered `Release artifacts` workflow. The final PR #54 head passed Quality #209.

The controlled publication path is defined in [RELEASING.md](RELEASING.md):

1. create `v0.3.0` from `4dc160c…`, not from later post-v0.3 `main`;
2. let the tag workflow validate and retain wheel/sdist/`SHA256SUMS`;
3. create the GitHub Release using exactly that bundle;
4. add a Trusted Publishing workflow that consumes those exact artifacts instead of rebuilding them;
5. configure PyPI Trusted Publisher;
6. publish and smoke-test `persistent-memory-mcp==0.3.0` from public PyPI;
7. submit stable package/release metadata to MCP Registry.

As reconciled on 2026-08-16, GitHub currently reports no tags and no releases for this repository, and `main` contains no PyPI publication workflow. Those steps therefore remain pending and must not be documented as already completed.

## Repository maintenance state

Stale draft PR #74 contains useful `SECURITY.md` and Dependabot configuration, but it is based on an obsolete branch and is conflictive. The correct path is to recreate those two improvements from current `main`, validate the new PR, then close the stale PR rather than force-merging old history.

## Product scope

Persistent Memory MCP is designed around one personal installation, SQLite by default, localhost-only Dashboard/Galaxy, project/local-owner isolation and MCP-compatible local development clients. Optional self-managed remote adapters do not change the product direction.

Not planned: workspace invitations, team-role hierarchies, billing/organization administration, public collaborative dashboards or automatic execution of repository code from stored memory.

## Next engineering order

1. Complete **MEM-33 / Issue #53** from the exact v0.3.0 release commit: tag → artifact gate → GitHub Release → Trusted Publishing → public smoke test → MCP Registry.
2. Recreate and validate the useful **security policy + Dependabot** changes from stale PR #74 on current `main`, then retire #74.
3. Reconcile **MEM-17 distribution scope**, keeping optional Docker/deployment work separate from the local-first product core.
4. Do not start another numbered product phase until release/distribution truth is synchronized across GitHub and Notion.
