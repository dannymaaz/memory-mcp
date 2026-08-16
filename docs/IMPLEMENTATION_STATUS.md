# Persistent Memory MCP implementation status

Last reconciled after the successful v0.3.0 GitHub Release publication on 2026-08-16. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The v0.3 technical foundation, the five-step Context Compiler phase, planned post-phase reliability/architecture work and the public GitHub v0.3.0 Release are complete.

Two intentionally separate lines now coexist:

- **v0.3.0 release line:** immutable MCP SDK v1 / `FastMCP` source at `9e0a084dd9b179612082edef99e1c3c9bf563ffa`, now tagged and published on GitHub;
- **post-v0.3 `main`:** MCP SDK v2 / `MCPServer` runtime with later reliability and maintenance work.

The remaining release work is external distribution, not missing product code:

- configure the matching PyPI Trusted Publisher;
- publish the exact verified GitHub Release wheel/sdist through OIDC without rebuilding;
- smoke-test a clean public PyPI install;
- submit stable metadata to MCP Registry;
- record final evidence and close Issue #53 / MEM-33.

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
| Application container / Tool Registry | Complete | PR #80 / Quality #346 | Extend composition only when justified |
| Security policy / dependency automation | Complete | PR #83 / Quality #352 | Routine maintenance |
| MCP SDK v1 release compatibility | Complete | PR #85 / Quality #360 | Frozen for v0.3.0 release line |
| MCP SDK v2 mainline runtime | Complete | PR #100 / MEM-42 / Quality #392 | Routine compatibility maintenance only |
| Immutable v0.3.0 source | Complete | PR #89 / Quality #361 / `9e0a084d...` | None for release source |
| Public GitHub v0.3.0 Release | Complete | PR #103 / Quality #401 / publisher `31979169557` | None |
| Repository PyPI publishing path | Complete / connector-ready | PR #91, PR #102, guarded `publish-pypi.yml` | PyPI Trusted Publisher account configuration |
| Distribution scope decision | Complete | MEM-17 | Optional future self-managed deployment docs only |
| Public PyPI publication | External/operational | GitHub Release + guarded OIDC workflow | Configure trust, publish exact assets, smoke-test |
| MCP Registry publication | Pending after PyPI | MEM-33 / Issue #53 | Stable public PyPI evidence first |
| Teams / public collaboration | Out of scope | explicit product decision | no implementation planned |

## Completed Context Compiler phase

1. ✅ Context Packet + model-aware token accounting — PR #60 / Quality #226.
2. ✅ Progressive repository retrieval — PR #62 / Quality #235.
3. ✅ Persistent code provenance and symbol evolution — PR #64 / Quality #250.
4. ✅ Context-quality regression guardrails — PR #66 / Quality #262.
5. ✅ Operational project map / risk-oriented Galaxy — PR #68 / Quality #282.

The phase tracker is closed. No sixth numbered phase item is implied.

## Post-phase reliability — complete

### Automatic Continuation Contract

PR #71 provides repository-bound project resolution, a bounded/redacted Continuation Contract v1 and one shared continuation path for explicit close, handoff and idle expiry.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination

PR #73 / MEM-30 provides bounded SQLite keyset paging with default 50 / hard maximum 200, opaque versioned cursors, query fingerprints, deterministic timestamp + `id` boundaries, snapshot anchoring and owner/project isolation.

See [PAGINATION.md](PAGINATION.md).

### Dashboard maintenance/UX

PR #77 / MEM-12 completed the localhost-only operational maintenance subset using existing Health, backup, restore and retention primitives. Quality #338 passed before merge `43790fdfe9c003a9347496a34b0360d17c95320b`.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application composition + Tool Registry

PR #80 / MEM-29 introduced `create_application(settings)` and one shared idempotent Tool Registry without changing public MCP tool contracts. Quality #346 passed before squash merge `f85b4d691ce1716b20ad7a49a02ca62227d03614`.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

### Security and dependency maintenance

PR #83 added `SECURITY.md` plus weekly Dependabot for Python/GitHub Actions and superseded stale PR #74. PR #102 later upgraded the verified PyPI artifact handoff to `actions/download-artifact@v8` after Quality #396 passed 16/16 jobs.

### MCP SDK v1 release compatibility

Issue #81 / PR #85 established the v0.3.0 release boundary:

```text
mcp>=1.28,<2
```

The release uses the real installed `FastMCP` v1 implementation. Quality #360 passed before merge `df854b6ff28c12aeb47a7bd53bed84429dcbc58c`.

This state is intentionally frozen in the immutable v0.3.0 release source.

### MCP SDK v2 mainline migration

Issue #88 / PR #100 / MEM-42 migrated post-v0.3 `main` to `mcp.server.MCPServer` and `mcp>=2,<3`, removed the silent MCP fallback, replaced private tool-registry mutation with public `remove_tool()` + `add_tool()`, and retained public tool/stdio contracts.

Quality #392 passed on final HEAD `23e819719516aa5c742535593e7cc2a3f77226c5`; PR #100 merged as `322a8838d4fa5102392bdcc042185334bfa78d4f`.

See [MCP_SDK_COMPATIBILITY.md](MCP_SDK_COMPATIBILITY.md).

## Local data-safety contracts

- **backup:** live SQLite uses SQLite's backup API and verifies integrity;
- **manifest:** SHA-256 sidecars contain bounded structural metadata, not memory contents;
- **health:** read-only integrity/foreign-key/index/disk checks;
- **restore:** preview → exact confirmation → fresh verified safety backup → atomic replacement → post-validation/rollback;
- **migration:** preview → checksum verification → verified backup → transactional explicit apply;
- **deletion:** exact scoped plan + short-lived single-use confirmation;
- **Dashboard maintenance:** localhost-only adapter reusing backup/restore/delete services rather than raw SQL;
- **context/repository:** bounded, provenance-aware and non-executing by default.

## v0.3.0 immutable release and GitHub publication

Release-only PR #89 produced the only valid v0.3.0 source:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

Quality #361 validated Ubuntu/Windows/macOS × Python 3.11–3.13, dependency audit, wheel/sdist, metadata, SHA-256, clean install and installed v0.2.0 upgrade.

PR #103 then added a guarded GitHub Release publisher. Exact-head Quality #401 passed 16/16 jobs and PR #103 merged as:

```text
4fff71ec44a40d7d4d296d4ad0b30d39583ea8f3
```

Publisher run `31979169557` completed successfully and created:

- annotated tag `v0.3.0` resolving exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- final GitHub Release `Persistent Memory MCP v0.3.0 — Data Safety and Recovery`;
- exact assets `persistent_memory_mcp-0.3.0-py3-none-any.whl`, `persistent_memory_mcp-0.3.0.tar.gz` and `SHA256SUMS`.

The workflow re-downloaded the draft Release assets and revalidated checksums/version/metadata before making the Release final.

Release: https://github.com/dannymaaz/memory-mcp/releases/tag/v0.3.0

The temporary connector branch trigger used for this one publication is retired afterward so future branch pushes cannot repeat GitHub Release creation.

## PyPI Trusted Publishing path

The canonical OIDC path was introduced in PR #91 and hardened in PR #102. The current `.github/workflows/publish-pypi.yml` is pinned to the already-published `v0.3.0` Release and:

1. accepts only an explicit v0.3.0 publication trigger;
2. requires the final non-draft/non-prerelease GitHub Release;
3. requires the tag to resolve exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
4. downloads wheel/sdist/`SHA256SUMS` from GitHub Release rather than rebuilding;
5. verifies SHA-256, package version/metadata and `twine check`;
6. passes only verified wheel/sdist through the Actions artifact boundary;
7. retrieves them with `actions/download-artifact@v8`;
8. publishes from environment `pypi` using OIDC with `id-token: write` only in the publication job.

For connector-driven completion, the workflow also accepts a push only on exact branch `release/publish-pypi-v0.3.0`. That branch must not be created until the corresponding PyPI Trusted Publisher is configured.

Required PyPI Trusted Publisher identity:

- owner: `dannymaaz`;
- repository: `memory-mcp`;
- workflow: `publish-pypi.yml`;
- environment: `pypi`.

## Remaining public release operations

1. Configure the matching PyPI Trusted Publisher.
2. Trigger the guarded PyPI workflow; publish the exact GitHub Release wheel/sdist via OIDC.
3. Install `persistent-memory-mcp==0.3.0` from public PyPI in a clean environment and smoke-test the documented CLI path.
4. Submit stable public metadata to MCP Registry.
5. Record final PyPI/Registry evidence in Issue #53 and Notion and close MEM-33.

Until successful public PyPI evidence exists, README installation must use repository/source installation rather than claiming the package is publicly installable.

## Distribution-scope decision — complete

MEM-17 defines the official boundary: core distribution stays **local-first and Python-first**, SQLite by default, local MCP clients and localhost-only Dashboard/Galaxy.

Docker, Render, Railway and equivalent platforms are not core requirements or release blockers. They may be documented later only as **self-managed** options where the operator owns network exposure, secrets, storage, TLS and backups. They must not imply an official hosted SaaS, shared workspaces, team roles, billing or a public multi-user Dashboard.

## Product scope

Persistent Memory MCP is designed around one personal installation, SQLite by default, localhost-only Dashboard/Galaxy, project/local-owner isolation and MCP-compatible local development clients. Optional self-managed remote adapters do not change the product direction.

Not planned: workspace invitations, team-role hierarchies, billing/organization administration, public collaborative dashboards or automatic execution of repository code from stored memory.

## Next engineering order

1. Complete Issue #53 / MEM-17 / MEM-33: PyPI Trusted Publisher → guarded OIDC publication → clean public PyPI smoke test → MCP Registry → final evidence.
2. Start no new numbered product phase until public release evidence and project records are synchronized.
