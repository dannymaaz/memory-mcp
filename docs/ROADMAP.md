# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system and Context Compiler for MCP-compatible development agents**. Product scope remains one personal installation, SQLite-first storage, localhost-only operational UI, project/owner isolation and no automatic repository code execution.

This document mirrors the canonical roadmap maintained in Notion.

## Status legend

- ✅ **Complete** — implemented, integrated, documented and validated by the required gate.
- 🟡 **In review** — repository work exists but a publication, final-head gate or external handoff remains.
- ⬜ **Planned** — sequenced work not started yet.
- ⛔ **Externally blocked** — repository work is ready but completion depends on external account configuration.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Data safety / recovery — ✅ Complete

- SQLite WAL + foreign keys;
- owner/project isolation and secret redaction;
- verified SQLite backups and SHA-256 manifests;
- read-only health diagnostics;
- two-phase confirmed restore with safety backup/rollback;
- versioned checksum-verified backup-first migrations;
- explicit upgrade CLI and fail-closed stale-schema startup;
- deterministic SQLite connection lifecycle.

### Packaging / upgrade safety — ✅ Complete

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

The five-step phase tracker is closed. No sixth numbered Context Compiler milestone is implied without a new roadmap decision.

## Post-phase reliability / architecture

### Automatic Continuation Contract — ✅ Complete

**Notion:** MEM-31 + remaining MEM-6 lifecycle gap  
**GitHub:** Issue #70 / PR #71  
**Gate:** Quality #290

Delivered repository-bound project resolution, Continuation Contract v1, one shared continuation path for explicit close/handoff/idle expiry, bounded/redacted state, Git identity without credentials and backward-compatible resume behavior.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination — ✅ Complete

**Notion:** MEM-30  
**GitHub:** Issue #72 / PR #73  
**Gate:** Quality #306

Delivered bounded SQLite keyset pagination with default 50 / hard max 200, opaque versioned cursors, query fingerprints, stable timestamp + `id` boundaries, first-page rowid snapshot anchoring, owner/project isolation, fail-closed malformed cursors, MCP history paging and Dashboard drill-down. The 10,000-record cross-platform evaluator remains part of reference CI.

See [PAGINATION.md](PAGINATION.md).

### Dashboard operational completion — ✅ Complete

**Notion:** MEM-12  
**GitHub:** Issue #76 / PR #77  
**Gate:** Quality #338  
**Merge:** `43790fdfe9c003a9347496a34b0360d17c95320b`

Delivered bounded owner/project-scoped maintenance status, safe localhost backup, signed restore preview/confirm, signed selective-deletion preview/confirm, explicit empty/error/loading states and hardened mutable HTTP routes while preserving the localhost-only product boundary.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application container + MCP Tool Registry — ✅ Complete

**Notion:** MEM-29  
**GitHub:** Issue #75 / PR #80  
**Gate:** Quality #346  
**Merge:** `f85b4d691ce1716b20ad7a49a02ca62227d03614`

PR #80 completed the first incremental architecture slice without rewriting the legacy server or changing public MCP contracts.

Delivered:

- `create_application(settings)` as the explicit runtime composition root;
- one shared idempotent `ToolRegistry` for dynamic MCP registration/replacement;
- deterministic initialization order exposed and covered by regression tests;
- Confirmed Deletion and Verified Restore/Maintenance migrated away from duplicated FastMCP registry mutation helpers;
- repeated construction/registration guarded against duplicate tools;
- registration failures made explicit instead of silently dropping required tools;
- current local-first scope, storage schema, destructive confirmation semantics and public tool names/signatures preserved.

Quality #346 passed Ubuntu/Windows/macOS × Python 3.11–3.13, lint/tests, agent regressions, token accounting, release-artifact/upgrade validation and dependency audit before merge.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

## Distribution / publication — 🟡 In review

**Notion:** MEM-17 + MEM-33  
**GitHub:** Issue #53

The **v0.3.0 release candidate preparation is complete**, but publication itself is not complete.

Verified repository state on 2026-08-16:

- package metadata is `0.3.0`;
- release preparation PR #54 is merged;
- the validated release merge commit is `4dc160c1fdf0e2858337239c42c9085fe8097493`;
- that release commit contains the tag-triggered `Release artifacts` workflow;
- the final PR #54 head passed Quality #209;
- upgrade/rollback/release documentation and checksum tooling are present;
- **no `v0.3.0` tag currently exists in GitHub**;
- **no GitHub Release currently exists**;
- **no PyPI Trusted Publishing workflow currently exists in `main`**.

Required controlled sequence:

1. create `v0.3.0` from the validated release commit `4dc160c…`, not from current post-v0.3 `main`;
2. require the tag workflow to build and validate wheel/sdist/`SHA256SUMS` successfully;
3. create the GitHub Release from that exact bundle;
4. add and validate a PyPI Trusted Publishing path that publishes those exact artifacts rather than rebuilding them;
5. configure the repository/account Trusted Publisher in PyPI;
6. publish and smoke-test `persistent-memory-mcp==0.3.0` from PyPI;
7. submit the stable package/release metadata to MCP Registry;
8. synchronize final publication evidence in GitHub docs and Notion.

The PyPI account trust relationship is an external dependency, but the missing tag/GitHub Release and missing publication workflow are repository/release tasks and must not be mislabeled as already complete.

MEM-17 still needs a product-scope decision separating optional Docker/deployment documentation from the local-first core.

See [RELEASING.md](RELEASING.md) and [UPGRADING.md](UPGRADING.md).

## Repository maintenance — ⬜ Planned cleanup

PR #74 contains useful `SECURITY.md` and Dependabot configuration but is based on an obsolete branch and is conflictive. Do not merge it as-is. Recreate the security policy and weekly pip/GitHub Actions dependency automation from current `main`, validate them, then close the stale PR.

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

1. Finish **MEM-33 / Issue #53** from the exact validated v0.3.0 release commit: tag → artifact gate → GitHub Release → PyPI Trusted Publishing → public smoke test → MCP Registry.
2. Recreate the useful **security policy + Dependabot** changes from stale PR #74 on current `main`, then retire the stale branch/PR.
3. Reconcile **MEM-17 distribution scope**, keeping optional deployment/Docker documentation separate from the local-first core.
4. Start no new numbered product phase until the release/distribution state and roadmap source of truth are coherent.
