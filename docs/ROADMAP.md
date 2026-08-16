# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system and Context Compiler for MCP-compatible development agents**. The product remains one personal installation, SQLite-first storage, localhost-only operational UI, project/owner isolation and no automatic execution of repository code.

This document is kept aligned with the canonical project records in Notion.

## Status legend

- ✅ **Complete** — implemented, integrated, documented and validated.
- 🟡 **In progress** — repository work is done or nearly done, but an operational/publication step remains.
- ⛔ **External dependency** — completion requires configuration or action outside this repository.
- ⬜ **Planned** — deliberate future work.
- 🚫 **Out of scope** — intentionally excluded.

## Delivered foundation — ✅ Complete

### Data safety and recovery

- SQLite WAL + foreign keys;
- owner/project isolation and secret redaction;
- WAL-safe verified SQLite backups and SHA-256 manifests;
- read-only health diagnostics;
- two-phase confirmed restore with safety backup/rollback;
- versioned checksum-verified backup-first migrations;
- explicit migration CLI and fail-closed stale-schema startup;
- deterministic SQLite connection lifecycle.

### Packaging and upgrade safety

- SQLite-first core with optional Supabase/PostgreSQL extras;
- immutable validated Runtime Settings;
- Ubuntu/Windows/macOS CI across Python 3.11–3.13;
- wheel/sdist clean-install validation;
- real installed v0.2.0 → v0.3/current data-preservation regression;
- release checksums and rollback documentation.

### Context Compiler phase

1. Context Packet + token accounting — PR #60 / MEM-36 / Quality #226.
2. Progressive repository retrieval — PR #62 / MEM-37 / Quality #235.
3. Persistent code provenance/symbol evolution — PR #64 / MEM-38 / Quality #250.
4. Context-quality/adversarial regression gates — PR #66 / MEM-39 / Quality #262.
5. Operational project map / risk-oriented Galaxy — PR #68 / MEM-40 / Quality #282.

The five-step phase is closed. No sixth Context Compiler milestone is implied without a new roadmap decision.

## Post-phase reliability and architecture — ✅ Complete

### Automatic Continuation Contract

**GitHub:** Issue #70 / PR #71  
**Gate:** Quality #290

Repository-bound project resolution, bounded/redacted continuation state and one shared continuation path for explicit close, handoff and idle expiry.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination

**GitHub:** Issue #72 / PR #73  
**Notion:** MEM-30  
**Gate:** Quality #306

Bounded SQLite keyset pagination with default 50 / hard max 200, opaque versioned cursors, query fingerprints, stable timestamp + `id` boundaries, first-page snapshot anchoring and owner/project isolation.

See [PAGINATION.md](PAGINATION.md).

### Dashboard operational completion

**GitHub:** Issue #76 / PR #77  
**Notion:** MEM-12  
**Gate:** Quality #338  
**Merge:** `43790fdfe9c003a9347496a34b0360d17c95320b`

Delivered localhost-only health/storage/backup status, safe backup, signed restore preview/confirm, signed selective-deletion preview/confirm and hardened mutable HTTP routes.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application container + MCP Tool Registry

**GitHub:** Issue #75 / PR #80  
**Notion:** MEM-29  
**Gate:** Quality #346  
**Merge:** `f85b4d691ce1716b20ad7a49a02ca62227d03614`

Delivered `create_application(settings)`, deterministic composition order and an idempotent shared Tool Registry. Confirmed Deletion and Verified Restore/Maintenance were migrated away from duplicated dynamic registration helpers without changing their public contracts.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

### MCP SDK v1 compatibility hotfix

**GitHub:** Issue #81 / PR #85  
**Notion:** MEM-41  
**Gate:** Quality #360  
**Merge:** `df854b6ff28c12aeb47a7bd53bed84429dcbc58c`

This was the compatibility boundary that made the v0.3.0 release line safe: the release candidate uses the MCP Python SDK v1 `FastMCP` API and is explicitly constrained to `mcp>=1.28,<2`.

That boundary remains part of the immutable v0.3.0 release candidate and is not rewritten by later `main` development.

### MCP SDK v2 runtime migration — ✅ Complete

**GitHub:** Issue #88 / PR #100  
**Notion:** MEM-42  
**Gate:** Quality #392  
**Merge:** `322a8838d4fa5102392bdcc042185334bfa78d4f`

Post-v0.3 `main` now uses the MCP Python SDK v2 `MCPServer` API:

- `src.server` imports the installed `mcp.server.MCPServer` directly;
- the local silent MCP fallback is removed;
- dependency policy is `mcp>=2,<3`;
- Tool Registry replacement uses public `remove_tool()` + `add_tool()` rather than private SDK registries;
- public tool names, arguments, payloads and stdio transport remain unchanged;
- real installed-SDK regressions exercise public tool listing/calling and replacement;
- no database, storage, Dashboard or destructive-confirmation contract changes.

Quality #392 passed on the exact final PR head after README, ROADMAP, IMPLEMENTATION_STATUS and MEM-17 distribution-scope reconciliation. Issue #88 is closed. The immutable v0.3.0 release candidate remains on its separate validated v1 boundary.

See [MCP_SDK_COMPATIBILITY.md](MCP_SDK_COMPATIBILITY.md).

## Repository maintenance — ✅ Complete

Stale draft PR #74 was not force-merged. Its useful security/dependency-maintenance changes were recreated from current `main` in PR #83, passed Quality #352 and merged as `25c7b7490ed309591af9b725114ad8f28375b298`.

Delivered:

- `SECURITY.md` aligned with the local-first threat model;
- weekly Dependabot updates for Python and GitHub Actions;
- grouped dependency updates to reduce PR noise.

PR #74 is closed as superseded.

## v0.3.0 distribution and publication — 🟡 In progress / ⛔ external dependency

**GitHub:** Issue #53  
**Notion:** MEM-17 + MEM-33

### Immutable release candidate — ✅ Complete

The original release preparation PR #54 produced merge `4dc160c1fdf0e2858337239c42c9085fe8097493`, but its MCP dependency could resolve MCP 2.x while the v0.3 runtime still used the v1 `FastMCP` API. It is therefore superseded as a tag target.

Release-only PR #89 applied only the compatibility repair to the isolated release state, without pulling later post-v0.3 product features into v0.3.0. Quality #361 passed the complete Ubuntu/Windows/macOS × Python 3.11–3.13 matrix, dependency audit, release-artifact validation, clean installs and real installed v0.2.0 upgrades.

The **only valid `v0.3.0` tag target** is:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

Do not tag current `main` and do not tag the superseded `4dc160c...` baseline. The MCP v2 migration in PR #100 is post-v0.3 work and must not alter this release target.

### Repository-side PyPI publication path — ✅ Complete

PR #91 was rebuilt from current `main`, pinned to the immutable release commit above and passed exact-head Quality #368. It was merged as:

```text
9f43944266b50706d6cb94809362b00d0c569017
```

`main` now contains a guarded manual PyPI Trusted Publishing workflow that:

- accepts only `release_tag=v0.3.0`;
- requires a final GitHub Release;
- requires that tag to resolve exactly to `9e0a084d...`;
- downloads wheel/sdist/`SHA256SUMS` from that GitHub Release instead of rebuilding;
- verifies checksums, package metadata and `twine check`;
- publishes only those verified distributions through OIDC from the protected `pypi` environment.

PR #84 and #90 were intentionally closed as superseded when their bases became stale. PR #91 is the canonical merged publication-preparation PR.

### Remaining publication sequence

1. Create annotated tag `v0.3.0` from `9e0a084dd9b179612082edef99e1c3c9bf563ffa`.
2. Require the tag-triggered Release artifacts workflow to finish successfully.
3. Download and verify wheel, sdist and `SHA256SUMS`.
4. Create the final GitHub Release using those exact artifacts.
5. Configure the matching PyPI Trusted Publisher for repository `dannymaaz/memory-mcp`, workflow `publish-pypi.yml`, environment `pypi`.
6. Run the guarded manual publication workflow.
7. Smoke-test a clean public install of `persistent-memory-mcp==0.3.0`.
8. Submit the stable package/release metadata to MCP Registry.
9. Record the final evidence in GitHub and Notion.

Until steps 1–7 are complete, the README must not imply that public PyPI installation is already available.

See [RELEASING.md](RELEASING.md) and [UPGRADING.md](UPGRADING.md).

## Distribution scope decision — ✅ Complete

MEM-17 already records the canonical scope decision: official core distribution stays **local-first and Python-first**. Docker, Render, Railway and equivalent platforms are optional future **self-managed** deployment documentation only; they are not v0.3.0 blockers and must not be presented as an official hosted SaaS.

There is no remaining internal product-definition task under MEM-17. The unfinished MEM-17/MEM-33 work is the same external publication sequence tracked by Issue #53: tag, verified release assets, GitHub Release, PyPI Trusted Publisher/public smoke test and MCP Registry.

## Product scope — 🚫 No collaborative SaaS

Persistent Memory MCP remains:

- one personal installation;
- local SQLite by default;
- localhost-only Dashboard/Galaxy;
- project/local-owner isolation;
- compatible with local MCP clients;
- optional self-managed remote storage adapters.

Workspace invitations, shared team roles, billing/organization administration and public collaborative dashboards are not roadmap milestones.

## Next recommended order

1. Complete **Issue #53 / MEM-17 / MEM-33** operational release steps: tag → artifact gate → GitHub Release → PyPI Trusted Publisher → publication → public smoke test → MCP Registry.
2. Start no new numbered product phase until release evidence and external distribution state are synchronized.

## Definition of done

A roadmap item is complete only when:

1. the path is integrated into the real product;
2. deterministic tests cover success, failure and boundaries;
3. the relevant Ubuntu/Windows/macOS gate passes;
4. measurable evidence exists for quality/cost/performance claims;
5. repository docs and Notion agree;
6. local-first/safety scope is not silently broadened;
7. publication claims are supported by actual public release/package evidence.
