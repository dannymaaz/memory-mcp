# Persistent Memory MCP implementation status

Last reconciled after PR #91 / Quality #368 on 2026-08-16. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The v0.3 technical foundation, the complete five-step Context Compiler phase and the planned post-phase reliability/architecture work are delivered. The repository now also contains the guarded PyPI Trusted Publishing path.

The principal unfinished work is **operational publication**, not application implementation:

- the immutable v0.3.0 release candidate is validated;
- the repository-side publication workflow is merged and validated;
- `v0.3.0` has not yet been tagged/published as a GitHub Release;
- PyPI Trusted Publisher account configuration and public publication remain external/operational steps;
- MCP Registry submission follows successful public PyPI validation.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| SQLite local-first storage | Complete | WAL, foreign keys, schema v2, backup-first migrations | Future numbered migrations as schema evolves |
| Backup / manifest / health / restore | Complete | PR #29/#35/#39/#43 | Optional rotation/signing refinements |
| Installed upgrade lifecycle | Complete | real v0.2.0 → v0.3/current package regressions | Future release migrations |
| Runtime Settings | Complete | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context Packet + token accounting | Complete | PR #60 / Quality #226 | Extend only as evidence contracts evolve |
| Progressive repository retrieval | Complete | PR #62 / Quality #235 | Ranking changes remain behind quality gates |
| Persistent symbol provenance/evolution | Complete | PR #64 / Quality #250 | Richer language relationships later |
| Context quality/adversarial gates | Complete | PR #66 / Quality #262 | Thresholds can tighten, not silently regress |
| Operational project map / Galaxy | Complete | PR #68 / Quality #282 | Optional UX refinement only |
| Automatic Continuation Contract | Complete | PR #71 / Quality #290 | Future fields only when justified |
| Deterministic keyset pagination | Complete | PR #73 / MEM-30 / Quality #306 | Optional remote-adapter parity if later required |
| Dashboard maintenance/UX | Complete | PR #77 / Quality #338 | Optional UX polish only |
| Application container / Tool Registry | Complete | PR #80 / Quality #346 | Migrate more integrations only when justified |
| Security policy / dependency automation | Complete | PR #83 / Quality #352 | Routine maintenance |
| MCP SDK v1 compatibility | Complete | PR #85 / Quality #360 | Deliberate MCP v2 migration tracked in #88 |
| Immutable v0.3.0 release candidate | Complete | PR #89 / Quality #361 / `9e0a084d...` | Operational tag/release creation |
| Repository PyPI publishing path | Complete | PR #91 / Quality #368 / `9f439442...` | External Trusted Publisher + release assets required |
| Public GitHub v0.3.0 release | Pending | Issue #53 | Tag exact release SHA, pass artifact workflow, create release |
| Public PyPI publication | External/operational | `publish-pypi.yml`, `docs/RELEASING.md` | Configure trust, publish exact assets, smoke-test |
| MCP Registry publication | Pending after PyPI | MEM-33 / Issue #53 | Stable public package/release URLs first |
| Teams / public collaboration | Out of scope | explicit product decision | no implementation planned |

## Completed Context Compiler phase

1. ✅ Context Packet + model-aware token accounting — PR #60 / Quality #226.
2. ✅ Progressive repository retrieval — PR #62 / Quality #235.
3. ✅ Persistent code provenance and symbol evolution — PR #64 / Quality #250.
4. ✅ Context-quality regression guardrails — PR #66 / Quality #262.
5. ✅ Operational project map / risk-oriented Galaxy — PR #68 / Quality #282.

The phase tracker is closed. No sixth numbered phase item is implied.

## Post-phase reliability

### Automatic Continuation Contract — complete

PR #71 provides repository-bound project resolution, a bounded/redacted Continuation Contract v1 and one shared continuation path for explicit close, handoff and idle expiry.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination — complete

PR #73 / MEM-30 provides bounded SQLite keyset paging with default 50 / hard maximum 200, opaque versioned cursors, query fingerprints, deterministic timestamp + `id` boundaries, snapshot anchoring and owner/project isolation.

See [PAGINATION.md](PAGINATION.md).

### Dashboard maintenance/UX — complete

PR #77 / MEM-12 completed the localhost-only operational maintenance subset using existing Health, backup, restore and retention primitives. Quality #338 passed before merge `43790fdfe9c003a9347496a34b0360d17c95320b`.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application composition + Tool Registry — complete

PR #80 / MEM-29 introduced `create_application(settings)` and one shared idempotent Tool Registry without rewriting the legacy server or changing public MCP tool contracts. Confirmed Deletion and Verified Restore/Maintenance were the first migrated integrations.

Quality #346 passed before squash merge `f85b4d691ce1716b20ad7a49a02ca62227d03614`.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

### Security and dependency maintenance — complete

PR #83 recreated the useful work from stale PR #74 on current `main`, added `SECURITY.md` plus weekly Dependabot for Python/GitHub Actions, passed Quality #352 and merged as `25c7b7490ed309591af9b725114ad8f28375b298`.

PR #74 is closed as superseded.

### MCP SDK compatibility — complete

Issue #81 identified that the previous broad MCP dependency could resolve MCP 2.x while the runtime still imported the v1 `mcp.server.fastmcp.FastMCP` API.

PR #85 now constrains the current runtime to:

```text
mcp>=1.28,<2
```

It adds regressions proving the installed FastMCP v1 implementation is used instead of the local fallback and that the MEM-29 Tool Registry works against the installed implementation.

Quality #360 passed on the exact PR head; squash merge: `df854b6ff28c12aeb47a7bd53bed84429dcbc58c`.

Issue #88 owns the future deliberate MCP v2 `MCPServer` migration.

## Local data-safety contracts

- **backup:** live SQLite uses SQLite's backup API and verifies integrity;
- **manifest:** SHA-256 sidecars contain bounded structural metadata, not memory contents;
- **health:** read-only integrity/foreign-key/index/disk checks;
- **restore:** preview → exact confirmation → fresh verified safety backup → atomic replacement → post-validation/rollback;
- **migration:** preview → checksum verification → verified backup → transactional explicit apply;
- **deletion:** exact scoped plan + short-lived single-use confirmation;
- **Dashboard maintenance:** localhost-only adapter reusing backup/restore/delete services rather than raw SQL;
- **context/repository:** bounded, provenance-aware and non-executing by default.

## v0.3.0 immutable release state

The original release preparation PR #54 produced `4dc160c1fdf0e2858337239c42c9085fe8097493`, but its broad MCP dependency was no longer safe as a release target.

Release-only PR #89 applied only the MCP SDK compatibility repair to that isolated candidate and intentionally excluded later post-v0.3 features. Exact-head Quality #361 passed:

- Ubuntu/Windows/macOS × Python 3.11–3.13;
- dependency audit;
- wheel/sdist build and metadata validation;
- SHA-256 generation/verification;
- clean wheel installation;
- real installed v0.2.0 → v0.3.0 upgrade validation.

PR #89 merged into `release/v0.3.0-final` as:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

This is the **only valid `v0.3.0` tag target**. Current `main` contains later features and must not be tagged as v0.3.0.

## PyPI Trusted Publishing path

Canonical PR #91 was recreated from current `main`, pinned to the immutable release commit and passed exact-head Quality #368. It was squash-merged as:

```text
9f43944266b50706d6cb94809362b00d0c569017
```

`main` now contains `.github/workflows/publish-pypi.yml` with these guards:

1. manual dispatch only;
2. exact tag `v0.3.0`;
3. final non-draft/non-prerelease GitHub Release required;
4. tag must resolve exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
5. wheel/sdist/`SHA256SUMS` are downloaded from the GitHub Release rather than rebuilt;
6. checksums, package version/metadata and `twine check` must pass;
7. only the verified distributions reach the isolated `pypi` environment job;
8. OIDC publication uses `id-token: write` only in that publish job.

PR #84 and #90 were intentionally superseded as their bases became stale. Neither was merged.

## Remaining public release operations

The controlled sequence from [RELEASING.md](RELEASING.md) is now:

1. create annotated `v0.3.0` from `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
2. require the tag-triggered release-artifact workflow to succeed;
3. verify wheel, sdist and `SHA256SUMS`;
4. create the GitHub Release using exactly those artifacts;
5. configure PyPI Trusted Publisher for owner `dannymaaz`, repository `memory-mcp`, workflow `publish-pypi.yml`, environment `pypi`;
6. run the guarded publication workflow;
7. install `persistent-memory-mcp==0.3.0` from public PyPI in a clean environment and smoke-test it;
8. submit stable public metadata to MCP Registry;
9. record final evidence in Issue #53 and Notion.

Until successful public PyPI evidence exists, README installation must use repository/source installation rather than claiming the package is publicly installable.

## Distribution-scope decision

MEM-17's remaining product decision is documentation-only: optional Docker/Render/Railway-style self-managed deployments may be documented separately, but they are not requirements of the local-first core and must not imply hosted multi-user SaaS support.

## Product scope

Persistent Memory MCP is designed around one personal installation, SQLite by default, localhost-only Dashboard/Galaxy, project/local-owner isolation and MCP-compatible local development clients. Optional self-managed remote adapters do not change the product direction.

Not planned: workspace invitations, team-role hierarchies, billing/organization administration, public collaborative dashboards or automatic execution of repository code from stored memory.

## Next engineering order

1. Complete Issue #53 / MEM-33 operational publication: exact tag → artifact gate → GitHub Release → Trusted Publisher → public PyPI smoke test → MCP Registry.
2. Resolve MEM-17 optional deployment documentation scope without changing the local-first product boundary.
3. Once the v0.3.0 release is stable, evaluate Issue #88 for deliberate MCP v2 migration.
4. Start no new numbered product phase until public release evidence and project records are synchronized.
