# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system and Context Compiler for MCP-compatible development agents**. Product scope remains one personal installation, SQLite-first storage, localhost-only operational UI, project/owner isolation and no automatic repository code execution.

This document mirrors the canonical roadmap maintained in Notion.

## Status legend

- ✅ **Complete** — implemented, integrated, documented and validated by the required gate.
- 🟡 **In review** — repository work exists but a publication, final-head gate or external handoff remains.
- ⬜ **Planned** — sequenced work not started yet.
- ⛔ **Externally blocked** — repository work is ready but completion depends on external account/UI configuration.
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

Delivered `create_application(settings)` as the explicit runtime composition root, one shared idempotent `ToolRegistry`, deterministic initialization order and migration of Confirmed Deletion + Verified Restore away from duplicated registry mutation helpers. Public tool contracts, local-first scope and destructive confirmation semantics were preserved.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

### MCP SDK v1 compatibility boundary — ✅ Complete

**GitHub:** Issue #81 / PR #85  
**Gate:** Quality #360  
**Merge:** `df854b6ff28c12aeb47a7bd53bed84429dcbc58c`

The current server implementation is explicitly constrained to `mcp>=1.28,<2`. Regression tests prove packaged runtime uses the installed `mcp.server.fastmcp.FastMCP` instead of silently selecting the local fallback, and validate Tool Registry registration/replacement against that installed implementation.

A deliberate migration to MCP v2 `MCPServer` is tracked separately in Issue #88 and must preserve public tools/stdio before the `<2` upper bound is removed.

See [MCP_SDK_COMPATIBILITY.md](MCP_SDK_COMPATIBILITY.md).

## Distribution / publication — 🟡 Repository ready; external release steps remain

**Notion:** MEM-17 + MEM-33  
**GitHub:** Issue #53

Repository-side preparation for v0.3.0 is now complete, but the actual public release is not.

### Immutable release source

The original prepared candidate `4dc160c1fdf0e2858337239c42c9085fe8097493` was superseded because its MCP dependency could resolve to v2 while the release code uses the v1 FastMCP API.

Release-only PR #89 applied only the required MCP compatibility repair to the isolated v0.3.0 branch and passed Quality #361. The **only valid tag target** is:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

Do not tag current `main` and do not tag the older `4dc160c…` candidate.

### Repository-side publication path — ✅ Complete

PR #91 passed exact-head Quality #368 and merged as `9f43944266b50706d6cb94809362b00d0c569017`.

`main` now contains the guarded manual PyPI Trusted Publishing workflow. It requires:

- input tag exactly `v0.3.0`;
- a non-draft/non-prerelease GitHub Release;
- that tag to resolve exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- wheel, sdist and `SHA256SUMS` downloaded from that GitHub Release rather than rebuilt;
- checksum, package-version and `twine check` verification;
- OIDC publication with `id-token: write` isolated to the `pypi` environment job.

See [RELEASING.md](RELEASING.md).

### Remaining controlled release sequence

As verified through the GitHub API on 2026-08-16, **no `v0.3.0` tag and no GitHub Release currently exist**.

Remaining steps:

1. create annotated `v0.3.0` from `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
2. require the tag-triggered Release artifacts workflow to build/validate wheel, sdist and `SHA256SUMS`;
3. verify the retained bundle;
4. create the GitHub Release from those exact artifacts;
5. configure PyPI Trusted Publisher for `dannymaaz/memory-mcp`, workflow `publish-pypi.yml`, environment `pypi`;
6. run the guarded manual publication workflow;
7. smoke-test `persistent-memory-mcp==0.3.0` from public PyPI in a clean environment;
8. submit stable public package/release metadata to MCP Registry;
9. synchronize final public-release evidence in GitHub docs and Notion.

The first four remaining items require actual release/tag state; PyPI trust configuration is an external account/UI dependency. None should be documented as complete without direct evidence.

MEM-17 keeps Docker/Render/Railway-style deployments optional/self-managed; they are not blockers for the local-first core.

## Repository maintenance — ✅ Current baseline complete

PR #83 recreated the useful security-maintenance work from current `main` and superseded stale PR #74.

Delivered:

- `SECURITY.md` aligned to the local-first threat model and private vulnerability reporting;
- weekly Dependabot updates for Python and GitHub Actions;
- grouped dependency update PRs to reduce maintenance noise.

PR #74 is closed and must not be revived or force-merged.

## Planned architecture follow-up

### MCPServer v2 migration — ⬜ Planned

**GitHub:** Issue #88

Migrate the v1 `FastMCP` runtime deliberately to MCP v2 `MCPServer`, adapt Tool Registry to supported v2 registration APIs, preserve stdio/public tool contracts and remove the temporary `<2` bound only after the full cross-platform and release-artifact gates pass.

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

1. Complete **MEM-33 / Issue #53** using only release target `9e0a084…`: tag → artifact gate → GitHub Release → Trusted Publishing → public smoke test → MCP Registry.
2. Reconcile **MEM-17 distribution scope** only for optional/self-managed deployment documentation; it does not block v0.3.0.
3. After the public v0.3.0 release is stable, schedule **Issue #88 MCPServer v2 migration** as a separate compatibility project.
4. Start no new numbered product phase until final release evidence is synchronized across GitHub and Notion.
