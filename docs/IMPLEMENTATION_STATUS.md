# Persistent Memory MCP implementation status

Last reconciled for PR #73 / MEM-30. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The v0.3 technical foundation and the complete five-step post-v0.3 Context Compiler phase are delivered. The product now has recoverable/versioned SQLite storage, hard context budgets, progressive repository retrieval, persistent code provenance, deterministic quality/adversarial CI gates and a bounded operational project map/Galaxy.

Two post-phase maintenance capabilities are also materially advanced:

- **automatic continuation — complete:** PR #71 / Quality #290 adds repository-bound project resolution plus Continuation Contract v1 shared by normal close, cross-interface handoff and idle expiry;
- **deterministic storage pagination — in review:** PR #73 / MEM-30 adds bounded keyset pagination to SQLite, local MCP history reads and Dashboard drill-down, with a 10,000-record cross-platform regression gate.

External release publication remains separately blocked on the user-side PyPI Trusted Publishing configuration before MCP Registry publication can proceed.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| SQLite local-first storage | Complete foundation | WAL, foreign keys, schema v2, backup-first migrations | Future numbered migrations as schema evolves |
| Backup / manifest / health / restore | Complete foundation | PR #29/#35/#39/#43 | Optional rotation/signing/UI refinements |
| Installed upgrade lifecycle | Complete | v0.2.0 → current package regression | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context Packet + token accounting | Complete | PR #60 / Quality #226 | Extend only as evidence contracts evolve |
| Progressive repository retrieval | Complete | PR #62 / Quality #235 | Ranking changes remain behind quality gates |
| Persistent symbol provenance/evolution | Complete | PR #64 / Quality #250 | Richer language relationships later |
| Context quality/adversarial gates | Complete | PR #66 / Quality #262 | Thresholds can tighten, not silently regress |
| Operational project map / Galaxy | Complete | PR #68 / Quality #282 | Additional UX refinement only |
| Automatic Continuation Contract | Complete | PR #71 / Quality #290 | Future richer checkpoint fields only when justified |
| Deterministic keyset pagination | **In review** | PR #73 / MEM-30 | Final exact-head cross-platform gate + merge |
| Hybrid search / embeddings | Complete foundation | semantic + lexical local fallback | Broader quality/cost benchmark corpus |
| Dashboard | Partial/advancing | PR #68 + PR #73 | Maintenance cards, explicit loading/empty/error UX |
| Application container / Tool Registry | Planned | MEM-29 | Reduce runtime wrapper/registration coupling |
| PyPI + MCP Registry publication | Externally blocked | MEM-33 / Issue #53 | Configure PyPI Trusted Publishing, publish, then registry |
| Teams / public collaboration | Out of scope | explicit product decision | no implementation planned |

## Completed post-v0.3 Context Compiler phase

1. ✅ **Context Packet + model-aware token accounting** — PR #60 / Quality #226.
2. ✅ **Progressive repository retrieval** — PR #62 / Quality #235.
3. ✅ **Persistent code provenance and symbol evolution** — PR #64 / Quality #250.
4. ✅ **Context-quality regression guardrails** — PR #66 / Quality #262.
5. ✅ **Operational project map / risk-oriented Galaxy** — PR #68 / Quality #282.

The phase tracker is closed. No sixth numbered phase item is implied by this document.

## Automatic Continuation Contract — complete

PR #71 / MEM-31 completed the lifecycle gap that remained after the original session foundation.

Continuation Contract v1 stores a bounded/redacted snapshot inside the checkpoint already created by `end_session`:

- objective;
- completed and pending work;
- blockers;
- relevant files;
- tests/validation;
- next safe action;
- Git branch/commit/dirty state;
- credential-free canonical remote identity and a bounded local-root fingerprint.

Project resolution checks owner-scoped repository remote/root bindings before historical slug fallback. Ambiguous strongest matches fail closed. Runtime ordering installs the continuation wrapper before Session Lifecycle, so explicit close, interface handoff and idle expiry use the same contract. `resume_project` preserves historical fields and adds the versioned continuation payload.

See [CONTINUATION.md](CONTINUATION.md). Quality #290 passed Ubuntu/Windows/macOS, Python 3.11–3.13, all reference evaluators, dependency audit and release-artifact upgrade checks on the exact final PR #71 HEAD.

## Deterministic keyset pagination — PR #73 / MEM-30

### Storage contract

PR #73 adds `SQLiteStorage.select_page()` while preserving historical `select()` for compatibility.

The new page contract provides:

- default page size **50**, hard maximum **200**;
- opaque versioned cursor;
- query fingerprint bound to table, filters, order column and direction;
- deterministic timestamp + `id` keyset boundary;
- allow-listed/validated order and filter columns;
- fail-closed malformed or cross-query cursors;
- an internal first-page SQLite rowid anchor so records inserted after traversal starts do not enter that traversal.

Same-timestamp regressions exercise thousands of records to prove the `id` tie-break prevents duplicates/skips.

### Product integrations

Local SQLite MCP runtime:

- `get_project_timeline(..., cursor=...)` keeps the historical response fields and adds page metadata;
- `list_project_history_page(...)` pages timeline, sessions, checkpoints, tasks, warnings and decisions with owner/project scope.

Dashboard:

- existing bounded multi-table snapshot remains the overview;
- `/api/table-page` provides owner/project-scoped read-only drill-down using the same SQLite keyset primitive;
- project ownership is validated before project-scoped reads;
- ambiguous multi-owner state without configured owner fails closed;
- Dashboard security headers remain intact.

Remote backends retain their legacy non-cursor path; PR #73 does not pretend SQLite cursor semantics are already implemented for optional remote adapters.

### Secret-redaction hardening

Pagination testing found a real safety gap: a payload such as `{"token": "secret-value"}` did not necessarily match provider-specific secret patterns. PR #73 extends recursive redaction so exact credential-bearing mapping keys redact otherwise-undetected scalar strings while preserving container shape and historical pattern labels. Existing redaction markers remain idempotent, and unrelated fields such as `token_count` remain visible.

### Reproducible pagination gate

`scripts/evaluate_storage_pagination.py` is wired into Ubuntu/Windows/macOS reference CI. Fixture:

- **10,000** active-owner/project tasks;
- **200** foreign-owner tasks;
- identical timestamps;
- page size **200**;
- a new matching record inserted after page 1.

Required properties:

- exactly 10,000 original records traversed;
- zero duplicates/skips;
- no foreign-owner data;
- exactly 50 pages;
- post-start insert excluded from the active traversal and visible to a fresh traversal;
- total traversal ≤ **5,000 ms**;
- every page ≤ **1,000 ms**.

Initial Ubuntu evidence before final documentation synchronization: **692.30 ms total**, **19.77 ms max page**, **13.79 ms mean page**. These are hosted-CI regression observations, not production SLA claims. Current evidence does not justify a new pagination index/migration.

See [PAGINATION.md](PAGINATION.md) for the detailed contract.

## Local data-safety contracts

- **backup:** live SQLite uses SQLite's backup API and verifies integrity;
- **manifest:** SHA-256 sidecars contain bounded structural metadata, not memory contents;
- **health:** read-only integrity/foreign-key/index/disk checks;
- **restore:** preview → exact confirmation → fresh verified safety backup → atomic replacement → post-validation/rollback;
- **migration:** preview → checksum verification → verified backup → transactional explicit apply;
- **deletion:** exact scoped plan + short-lived confirmation;
- **context/repository:** bounded, provenance-aware and non-executing by default.

## Product scope

Persistent Memory MCP is designed around one personal installation, SQLite by default, localhost-only operational UI, project/local-owner isolation and MCP-compatible local development clients. Optional self-managed remote adapters do not change the product direction.

Not planned: workspace invitations, team-role hierarchies, billing/organization administration, public collaborative dashboards or automatic execution of repository code from stored memory.

## Next engineering order

1. Finish PR #73 / MEM-30 exact-head Quality and merge if green.
2. Reconcile MEM-12 Dashboard against the pagination work; keep only remaining maintenance/UX gaps.
3. Implement MEM-29 incrementally: `create_application(settings)` + explicit idempotent MCP Tool Registry, starting with Maintenance/Deletion instead of a rewrite.
4. Reconcile MEM-17 distribution scope against the already-complete v0.3 release foundation.
5. MEM-33/Issue #53 remains blocked on PyPI Trusted Publishing configuration, then MCP Registry publication.
