# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system and Context Compiler for MCP-compatible development agents**. Product scope remains one personal installation, SQLite-first storage, localhost-only operational UI, project/owner isolation and no automatic repository code execution.

This document mirrors the canonical roadmap maintained in Notion.

## Status legend

- ✅ **Complete** — implemented, integrated, documented and validated by the required gate.
- 🟡 **In review** — implementation exists but the exact final-head gate/merge is still open.
- ⬜ **Planned** — sequenced work not started yet.
- ⛔ **Externally blocked** — repository work is ready but completion depends on an external user/account configuration.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Data safety / recovery — ✅

- SQLite WAL + foreign keys;
- owner/project isolation and secret redaction;
- verified SQLite backups and SHA-256 manifests;
- read-only health diagnostics;
- two-phase confirmed restore with safety backup/rollback;
- versioned checksum-verified backup-first migrations;
- explicit upgrade CLI and fail-closed stale-schema startup;
- deterministic SQLite connection lifecycle.

### Packaging / upgrade safety — ✅

- SQLite-first core with optional Supabase/PostgreSQL extras;
- immutable validated Settings foundation;
- Ubuntu/Windows/macOS CI across Python 3.11–3.13;
- wheel/sdist clean-install validation;
- installed v0.2.0 → current schema data-preservation regression;
- release checksums and rollback documentation.

### Context Compiler phase — ✅ Complete

1. **Context Packet + token accounting** — PR #60 / MEM-36 / Quality #226.
2. **Progressive repository retrieval** — PR #62 / MEM-37 / Quality #235.
3. **Persistent code provenance/symbol evolution** — PR #64 / MEM-38 / Quality #250.
4. **Context-quality/adversarial regression gates** — PR #66 / MEM-39 / Quality #262.
5. **Operational project map / risk-oriented Galaxy** — PR #68 / MEM-40 / Quality #282.

The umbrella tracker for this five-step phase is closed. No additional numbered Context Compiler milestone should be inferred without a new roadmap decision.

## Post-phase reliability / architecture work

### Automatic Continuation Contract — ✅ Complete

**Notion:** MEM-31 + completion of remaining MEM-6 gap  
**GitHub:** Issue #70 / PR #71  
**Gate:** Quality #290

Delivered:

- owner-scoped repository binding by canonical remote/local root before slug creation;
- ambiguous strongest binding fails closed;
- versioned bounded/redacted Continuation Contract inside the existing session-close checkpoint;
- objective, completed/pending work, blockers, files, tests, next action and Git state;
- credential-free canonical remote plus bounded root fingerprint rather than absolute path in continuation output;
- one shared continuation path for explicit close, cross-interface handoff and idle expiry;
- backward-compatible `resume_project` extension.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination — ✅ Complete

**Notion:** MEM-30  
**GitHub:** Issue #72 / PR #73  
**Gate:** Quality #306 on the final functional/documented implementation before state-only reconciliation.

PR #73 replaces new high-volume all-row/offset-style reads with a stable bounded SQLite keyset contract while keeping historical `select()` compatibility.

Delivered:

- `StoragePage` with default 50 / hard max 200;
- opaque versioned cursor;
- fingerprint bound to table, filters, order and direction;
- deterministic timestamp + `id` boundary;
- first-page rowid anchor that freezes traversal against later inserts;
- malformed/cross-query cursors fail closed;
- order/filter identifiers validated against allow lists/schema;
- MCP history pagination for timeline, sessions, checkpoints, tasks, warnings and decisions;
- localhost Dashboard `/api/table-page` drill-down using the same storage primitive;
- owner/project isolation and multi-owner fail-closed behavior;
- recursive sensitive-field redaction hardening discovered through pagination regressions;
- cross-platform 10,000-record pagination evaluation wired to reference CI.

Regression fixture:

- 10,000 active-owner records + 200 foreign-owner records;
- all focus rows share the same timestamp;
- 50 pages of 200;
- one new matching row inserted after page 1.

Quality #306 verified exact traversal without duplicates/skips/foreign rows, stable snapshot semantics, the complete Python 3.11–3.13 × Ubuntu/Windows/macOS matrix, reference evaluators, dependency audit and wheel/sdist upgrade checks. Observed pagination traversal remained far below the 5,000 ms total / 1,000 ms per-page guardrails; current evidence does not justify a new index/migration.

See [PAGINATION.md](PAGINATION.md).

### Dashboard operational completion — ✅ Complete

**Notion:** MEM-12  
**GitHub:** Issue #76 / PR #77  
**Gate:** Quality #338  
**Merge:** `43790fdfe9c003a9347496a34b0360d17c95320b`

PR #77 closed the genuine Dashboard maintenance/UX subset without changing the local-first product boundary.

Delivered:

- owner/project-scoped maintenance status built on `HealthService` rather than duplicated checks;
- health, storage/free-disk, latest verified backup, persisted verification-risk and sensitivity cards;
- explicit empty/error/loading states;
- existing bounded snapshot plus PR #73 keyset drill-down;
- safe localhost backup action with server-generated destination inside explicit `--backup-dir`;
- restore as signed `preview → confirm`, delegating to the existing verified restore/safety-backup/rollback service;
- selective deletion as signed `preview → confirm`, at most 100 explicit IDs, sharing the consumed confirmation state with the MCP deletion interface;
- JSON-only POST surface, 64 KiB request cap and explicit `X-Memory-MCP-Action: 1` header;
- restrictive CSP with same-origin `connect-src` for the local UI;
- no arbitrary filesystem paths, raw SQL or public/remote Dashboard behavior.

Quality #338 passed the final documentation HEAD across Ubuntu/Windows/macOS × Python 3.11–3.13, reference evaluators, dependency audit and release-artifact/upgrade validation before PR #77 was merged. Issue #76 and Notion MEM-12 are closed/completed.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application container + MCP Tool Registry — ⬜ Planned

**Notion:** MEM-29  
**GitHub:** Issue #75

Goal: reduce accumulated runtime ordering/monkey-patching coupling incrementally, not rewrite the server.

Acceptance direction:

- `create_application(settings)` composition root;
- explicit idempotent Tool Registry;
- initialization order documented and tested;
- start by moving Maintenance/Deletion off dynamic wrappers;
- preserve public tool contracts and current local-first behavior.

### Distribution / publication — mixed

**Notion:** MEM-17 + MEM-33  
**GitHub:** Issue #53

Already complete: package build, release artifacts, checksums, clean installs, upgrade regressions, GitHub release foundation and recovery documentation.

**Externally blocked:** PyPI Trusted Publishing must be configured for the repository/account. After PyPI publication is public, MCP Registry publication can proceed. Do not treat this external dependency as unfinished application code.

MEM-17 still needs a product-scope decision separating optional Docker/deployment documentation from the local-first core.

## Product scope decision — 🚫 No collaborative SaaS

Persistent Memory MCP remains:

- one personal installation;
- local SQLite by default;
- localhost-only Dashboard/Galaxy;
- project/local-owner isolation;
- compatible with local MCP clients;
- optional self-managed remote storage adapters without changing the core direction.

Workspace invitations, shared team roles, billing/organization administration and public collaborative dashboards are not roadmap milestones.

## Definition of done

A roadmap item is not complete until:

1. the path is integrated into the real product rather than only a helper;
2. deterministic tests cover success, failure and boundaries;
3. the relevant Ubuntu/Windows/macOS gate passes;
4. measurable evidence exists for quality/cost/performance claims;
5. repository docs and Notion agree;
6. local-first/safety scope is not silently broadened.

## Current recommended order

1. Implement **MEM-29 / Issue #75 Application container + Tool Registry** incrementally, beginning with Maintenance/Deletion registration coupling.
2. Reconcile **MEM-17 distribution scope** against already-delivered v0.3 release/recovery work.
3. Complete **MEM-33 / Issue #53** only after PyPI Trusted Publishing is configured, then publish to MCP Registry.
