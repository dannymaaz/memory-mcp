# Persistent Memory MCP implementation status

Last reconciled after PR #91 / Quality #368 merged into `main`. Persistent Memory MCP remains a **local-first, personal, SQLite-first and localhost-only** product.

## Executive summary

The v0.3 technical foundation, the complete five-step Context Compiler phase and the post-phase reliability/architecture work are delivered. The product now includes recoverable/versioned SQLite storage, automatic continuation, deterministic keyset pagination, Dashboard maintenance/UX, an explicit Application composition root with idempotent MCP Tool Registry, a tested MCP SDK v1 compatibility boundary and repository-side guarded PyPI Trusted Publishing.

The principal unfinished work is now the **actual public v0.3.0 release sequence**, not application code or repository publication plumbing. The immutable v0.3.0 candidate is `9e0a084dd9b179612082edef99e1c3c9bf563ffa`; no `v0.3.0` tag or GitHub Release currently exists.

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
| Dashboard maintenance/UX | Complete | PR #77 / MEM-12 / Quality #338 | Future optional UX polish only |
| Application container / Tool Registry | Complete | PR #80 / MEM-29 / Quality #346 | Migrate additional integrations only when justified |
| MCP SDK v1 compatibility | Complete | PR #85 / Issue #81 / Quality #360 | Deliberate MCPServer v2 migration tracked in #88 |
| Security / dependency automation | Complete | PR #83 | Ongoing Dependabot review only |
| v0.3.0 release candidate | Complete | PR #89 / Quality #361 / `9e0a084…` | Create the actual tag/release from this exact commit |
| Repository-side PyPI publication path | Complete | PR #91 / Quality #368 | External tag/release/PyPI trust state required |
| Public PyPI publication | Pending external release sequence | Issue #53 | Tag, GitHub Release, Trusted Publisher, guarded publish, clean smoke test |
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

PR #71 / MEM-31 completed the lifecycle gap after the original session foundation. Continuation Contract v1 stores a bounded/redacted checkpoint containing objective, completed/pending work, blockers, relevant files, validation, next safe action and credential-free Git identity. Repository-bound project resolution fails closed on ambiguous strongest matches, and explicit close, handoff and idle expiry share the same continuation path.

See [CONTINUATION.md](CONTINUATION.md).

### Deterministic keyset pagination — complete

PR #73 / MEM-30 adds bounded SQLite keyset paging while preserving historical `select()` compatibility. It is integrated into MCP history reads and localhost Dashboard drill-down, with the 10,000-record cross-platform reference evaluator proving exact traversal without duplicate/skip/scope leakage.

See [PAGINATION.md](PAGINATION.md).

### Dashboard maintenance/UX — complete

PR #77 / MEM-12 completed the genuine Dashboard operations subset while keeping the interface localhost-only. It reuses `HealthService`, backup/restore/retention primitives and signed confirmations rather than introducing raw mutation paths.

Quality #338 passed before merge `43790fdfe9c003a9347496a34b0360d17c95320b`.

See [DASHBOARD_MAINTENANCE.md](DASHBOARD_MAINTENANCE.md).

### Application composition + Tool Registry — complete

PR #80 / MEM-29 introduced the explicit architecture boundary without a flag-day server rewrite. `create_application(settings)` owns the real runtime composition path and `ToolRegistry` centralizes idempotent dynamic MCP registration/replacement. Confirmed Deletion and Verified Restore/Maintenance are the first integrations moved away from duplicated private registry helpers.

Quality #346 passed before merge `f85b4d691ce1716b20ad7a49a02ca62227d03614`.

See [APPLICATION_COMPOSITION.md](APPLICATION_COMPOSITION.md).

### MCP SDK compatibility — complete for current v1 runtime

PR #85 / Issue #81 fixed a real dependency/runtime mismatch: the server code uses MCP SDK v1 `FastMCP`, while an unconstrained dependency could resolve to MCP v2 and silently trigger the repository fallback.

Current packaged contract:

- `mcp>=1.28,<2`;
- tests prove `src.server.server` is the installed `mcp.server.fastmcp.FastMCP` implementation;
- Tool Registry register/replace behavior is validated against that installed FastMCP;
- Quality #360 passed the exact documentation HEAD before merge `df854b6ff28c12aeb47a7bd53bed84429dcbc58c`.

Issue #88 separately tracks the deliberate MCP v2 `MCPServer` migration. The `<2` bound must not be removed before that migration passes all compatibility/release gates.

See [MCP_SDK_COMPATIBILITY.md](MCP_SDK_COMPATIBILITY.md).

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

### Final release candidate

The original candidate `4dc160c1fdf0e2858337239c42c9085fe8097493` is no longer the tag target because it predates the final MCP SDK compatibility repair.

Release-only PR #89 was applied directly to the isolated release branch and changed only the release-critical compatibility boundary. Quality #361 passed across Ubuntu/Windows/macOS × Python 3.11–3.13, dependency audit, release artifact builds, checksum validation, clean installs and real v0.2.0 upgrades.

The **only valid v0.3.0 tag target** is:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

Direct comparison against the original release candidate shows one release-only commit affecting the MCP constraint, compatibility regression and release/change documentation; it does not import later post-v0.3 features.

### Repository-side PyPI publication path — complete

PR #91 passed Quality #368 on exact head `084f9cff8a2d9d253e673e60ede9cb74ca2dde6b` and merged into `main` as `9f43944266b50706d6cb94809362b00d0c569017`.

`main` now contains `.github/workflows/publish-pypi.yml`, which:

- is manual via `workflow_dispatch`;
- accepts only `v0.3.0` for this release;
- requires a real non-draft/non-prerelease GitHub Release;
- requires that tag to resolve exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- downloads wheel/sdist/`SHA256SUMS` from the GitHub Release instead of rebuilding;
- verifies SHA-256, release version and `twine check`;
- passes only the verified wheel/sdist to the isolated `pypi` environment job;
- grants `id-token: write` only to that publication job and publishes through Trusted Publishing/OIDC.

See [RELEASING.md](RELEASING.md).

### Remaining publication steps

GitHub API verification on 2026-08-16 still reports **no `v0.3.0` tag and no GitHub Release**. Therefore the public release is not complete.

Remaining sequence:

1. create annotated `v0.3.0` exactly from `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
2. require `.github/workflows/release.yml` to build/validate the tag artifacts;
3. verify the retained wheel, sdist and `SHA256SUMS` bundle;
4. create the GitHub Release with exactly that bundle;
5. configure PyPI Trusted Publisher for owner `dannymaaz`, repository `memory-mcp`, workflow `publish-pypi.yml`, environment `pypi`;
6. run the guarded publication workflow;
7. install `persistent-memory-mcp==0.3.0` from public PyPI in a clean environment and smoke-test the CLI;
8. submit stable public metadata to MCP Registry;
9. reconcile final public-release evidence in repository docs and Notion.

The available connected GitHub tools in this maintenance session do not expose tag or GitHub Release creation, so those actions must not be simulated with branches or marked complete without actual external evidence.

## Repository maintenance state

PR #83 completed the previously stale security/dependency-maintenance work from current `main`:

- `SECURITY.md` documents supported versions, private reporting and the local-first security boundary;
- weekly Dependabot updates cover Python and GitHub Actions;
- dependency updates are grouped to reduce noise.

Stale PR #74 is closed as superseded and should not be revived.

## Product scope

Persistent Memory MCP is designed around one personal installation, SQLite by default, localhost-only Dashboard/Galaxy, project/local-owner isolation and MCP-compatible local development clients. Optional self-managed remote adapters do not change the product direction.

Not planned: workspace invitations, team-role hierarchies, billing/organization administration, public collaborative dashboards or automatic execution of repository code from stored memory.

## Next engineering order

1. Complete **MEM-33 / Issue #53** from exact release target `9e0a084…`: tag → artifact gate → GitHub Release → Trusted Publishing → public smoke test → MCP Registry.
2. Keep **MEM-17** optional deployment/Docker documentation separate from the local-first core and from the v0.3.0 release gate.
3. After the public release is stable, schedule **Issue #88** as the deliberate MCPServer v2 compatibility project.
4. Do not start another numbered product phase until release/distribution evidence is synchronized across GitHub and Notion.
