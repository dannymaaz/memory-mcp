# Persistent Memory MCP delivery roadmap

This roadmap reflects merged work through PR #52 plus the v0.3.0 release candidate in PR #54. Persistent Memory MCP is a local-first personal application: one local installation, one private localhost dashboard and no shared workspace or multi-user role model.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end refinements remain.
- ⬜ **Planned** — not implemented yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Product CLI and local onboarding — ✅ Complete foundation

- `memory-mcp` and `persistent-memory-mcp` command aliases.
- `init`, `doctor`, `status`, `health` and `serve` commands.
- `memory-mcp-migrate` for explicit SQLite migration preview/apply.
- Safe client configuration with backup, rollback and uninstall support.
- Ubuntu, Windows and macOS CI across Python 3.11–3.13.
- Wheel/sdist build and clean-install validation on Ubuntu, Windows and macOS.
- Real installed v0.2.0 → candidate upgrade validation on all three operating systems.

Remaining release work:

- validate and merge the exact v0.3.0 release candidate;
- build the exact tagged release bundle and SHA-256 manifest;
- publish GitHub Release/PyPI artifacts and prepare MCP Registry submission.

### Local storage and isolation — ✅ Complete

- SQLite storage with WAL, foreign keys and scoped operations.
- Owner/project isolation on runtime reads and writes.
- Optional self-managed Supabase/PostgreSQL adapters.
- Import/export compatibility and packaged local schema.
- Versioned local migration framework with checksum tracking.
- Deterministic close semantics for context-managed SQLite connections.

### Security and retention — ✅ Complete

- Secret redaction, including nested dictionaries, lists and tuples.
- Stored-instruction detection, sensitivity and expiry metadata.
- Scope-validated retention candidate selection.
- Two-phase selective deletion and retention execution from PR #26.
- Exact record previews, signed short-lived confirmation tokens and plan fingerprints.
- Rejection of altered, expired, cross-scope or reused plans.
- Exact ID deletion, pre-mutation revalidation and audit metadata without deleted content.

### Verified SQLite backup, health and recovery — ✅ Complete foundation

PR #29 established recoverable local backup creation:

- backups use `sqlite3.Connection.backup()` instead of copying the live file;
- active WAL-mode databases are supported;
- source/destination collisions and accidental overwrite are rejected;
- incomplete temporary files are cleaned after failures;
- each completed copy must pass `PRAGMA integrity_check`;
- results expose bounded structural metadata without stored memory values.

PR #35 added independent backup verification:

- versioned JSON manifests;
- SHA-256 digest verification;
- package, SQLite and schema version metadata;
- bounded table counts and integrity result;
- tamper, malformed-manifest and incompatible-version detection;
- no memory values or source database paths in manifests.

PR #39 added read-only SQLite health and maintenance-readiness diagnostics:

- bounded `PRAGMA quick_check` on every report;
- optional full `PRAGMA integrity_check`;
- foreign-key violation detection;
- expected-index validation;
- DB/WAL/SHM sizes and free disk space;
- latest verified SHA-256 backup awareness;
- safe JSON output without memory values or the absolute active database path.

PR #43 added confirmed two-phase restore, and PR #46 completed cross-platform hardening:

- restore plans validate the selected verified backup, schema compatibility and available disk space;
- HMAC confirmation is short-lived, plan-bound and single-use;
- the active database receives a fresh verified safety backup before replacement;
- logical SQLite state is fingerprinted through a consistent WAL-aware snapshot, avoiding false drift from filesystem metadata changes;
- WAL/SHM sidecars are cleared with bounded retry behavior and persistent locks fail closed;
- replacement is atomic and post-restore validation is mandatory;
- automatic rollback restores the pre-restore safety backup if post-replacement validation fails.

### Versioned SQLite upgrades — ✅ Complete

PR #45 added the formal local migration framework. PR #51 integrated that framework into the installed product.

- read-only migration preview;
- `schema_migrations` history and stable SHA-256 checksums;
- future/inconsistent schema-history rejection;
- verified backup before pending migrations are applied;
- transaction-per-migration execution;
- installed `memory-mcp-migrate` preview/apply command;
- mutation requires explicit `--apply --yes`;
- MCP startup inspects migration state read-only and refuses stale existing databases instead of automigrating;
- genuinely new empty SQLite databases bootstrap directly to the packaged current schema/history;
- existing databases are never silently marked current;
- the exact historical v0.2.0 package is installed in CI, real data is created, the candidate is installed, the stale schema is blocked, the explicit migration is applied and the original data is verified on Ubuntu, Windows and macOS.

PR #52 additionally makes `with storage.connect()` preserve native commit/rollback behavior while closing the connection deterministically at context exit, reducing WAL/SHM handle lifetime and GC dependence.

### Context, search and embeddings — ✅ Complete foundation

- Intent-aware context and token budgets.
- Semantic and lexical hybrid search.
- Persisted embedding fingerprints, bounded reindexing, retries and local fallback.
- Token-savings and regression metrics.

Remaining refinements:

- background indexing;
- broader search-quality and provider-cost benchmarks.

### Session continuity — 🟡 Partial

Completed:

- session reuse, heartbeat and stale-session closure;
- cross-client handoff and checkpoints.

Remaining:

- fully automatic project resolution at session start;
- automatic milestone capture before shutdown or context exhaustion;
- complete local continuation contract and quality validation.

### Git verification and code intelligence — 🟡 Partial

Completed:

- repository, branch, commit, file and working-tree verification;
- stale, contradicted, missing-source and unverified states;
- Python, JavaScript, TypeScript and SQL symbol extraction;
- bounded impact graphs.

Remaining:

- persistent symbol history across revisions;
- moved, renamed and deleted symbol tracking;
- links from symbols to tests, tasks and deployments.

### Duplicate, contradiction and deployment safety — ✅ Complete foundation

- Duplicate and contradiction recommendations with evidence and confidence.
- Deployment history and exact-target validation.
- Risk classification, confirmation gates and rollback plans.
- Evaluation and provenance regression suite.

### Local dashboard and Galaxy View — 🟡 Partial

Completed:

- localhost-only dashboard;
- read-only project, session, decision, task, warning, retention and deployment views;
- bounded filtering and JSON/CSV export;
- Galaxy knowledge visualization with bounded graphs;
- confirmed deletion and verified restore are available through safe MCP maintenance workflows.

Remaining refinements:

- explicit pagination cursors;
- operational summary cards for storage, staleness, verification and sensitivity;
- polished empty, loading and error states;
- dashboard controls for backup, restore and confirmed deletion that consume existing safety gates without bypassing them.

## Product scope decision

### Teams, memberships, roles and remote collaborative dashboard — 🚫 Out of scope

PR #23 was closed without merge and issue #22 was closed as not planned.

The product remains:

- a personal local installation;
- backed by private local SQLite by default;
- accessed through local MCP clients;
- visualized through a localhost-only dashboard;
- isolated by project and local owner identity.

Workspace invitations, team roles, shared memory, public remote dashboards, billing and organization administration are not milestones.

## v0.3.0 — Data Safety and Recovery

### 1. Verified backup creation and manifests — ✅ Complete

- [x] Consistent WAL-safe SQLite backup — PR #29 / issue #28.
- [x] Integrity validation and bounded metadata — PR #29.
- [x] Versioned SHA-256 manifest and tamper verification — PR #35 / issue #31.

### 2. Database health and integrity — ✅ Complete

- [x] `memory-mcp health` — PR #39 / issue #32.
- [x] Bounded `quick_check` and optional full `integrity_check`.
- [x] Foreign-key and expected-index validation.
- [x] Database/WAL/SHM size, schema version and available disk space.
- [x] Latest verified backup discovery without memory contents.
- [x] Maintenance-readiness state requiring healthy structure and a verified backup.

### 3. Two-phase verified restore — ✅ Complete

- [x] Backup checksum/integrity/schema/space validation — PR #43.
- [x] Exact preview and HMAC-bound explicit confirmation.
- [x] Fresh verified safety backup immediately before replacement.
- [x] WAL-aware logical-state fingerprinting for drift detection — PR #46.
- [x] Atomic replacement and automatic rollback after failed post-restore validation.
- [x] Fail-closed busy checkpoint/persistent sidecar handling.
- [x] Ubuntu/Windows/macOS Python 3.11–3.13 validation.

### 4. Versioned SQLite migrations and installed upgrade lifecycle — ✅ Complete

- [x] `schema_migrations` tracking and ordered packaged migrations — PR #45.
- [x] SHA-256 checksums and altered/inconsistent history detection.
- [x] Transactional migration execution and verified pre-migration backup.
- [x] Installed `memory-mcp-migrate` preview/apply command — PR #51.
- [x] Startup guard that never automigrates stale existing databases.
- [x] Safe current-schema bootstrap only for genuinely new empty databases.
- [x] Real installed historical v0.2.0 → candidate upgrade with preserved data on Ubuntu, Windows and macOS — Quality #200.
- [x] Deterministic context-managed SQLite close semantics — PR #52 / Quality #202.

### 5. Configuration and package cleanup — ✅ Complete foundation

PR #30 aligned packaging with the local-first direction:

- SQLite is the normal default;
- Supabase/PostgreSQL drivers are optional extras;
- Ubuntu/Windows/macOS CI covers Python 3.11–3.13;
- dependency audit covers core and optional remote extras.

PR #47 completed Issue #37's Settings foundation:

- immutable validated `RuntimeSettings`;
- SQLite as the Settings default;
- `MEMORY_BACKEND` canonical;
- `MEMORY_STORAGE_BACKEND` retained as a transitional alias with `FutureWarning`;
- conflicting aliases fail closed;
- secrets are masked with `SecretStr`;
- validated backend/path/startup settings can be injected into storage/restore.

PR #51 uses `RuntimeSettings` for startup migration readiness and database path/backend selection. Provider/subsystem-specific environment variables remain incremental refactor territory rather than a v0.3.0 release blocker.

### 6. Release artifact validation — ✅ Complete foundation

PR #41 established real artifact validation:

- wheel and sdist build with `python -m build`;
- `twine check`;
- clean installed-wheel tests outside the source checkout;
- installed `init`, `doctor`, `status` and `health` smoke tests;
- Ubuntu/Windows/macOS coverage.

PR #51 extends the release gate with the real historical 0.2.0 installed upgrade lifecycle.

PR #54 release candidate adds:

- package version `0.3.0` validation in editable and built artifacts;
- SHA-256 generation/verification for wheel and sdist;
- release notes and backup-first upgrade/rollback documentation;
- a tag-triggered workflow that rebuilds and validates the exact tag before retaining the release bundle.

### 7. Dashboard completion — ⬜ Planned refinement

- Add pagination, summary cards and accessible maintenance workflows.
- Surface backup health, last verified backup and database size.
- Integrate confirmed deletion and restore previews without bypassing safety gates.

### 8. Automatic continuation completion — ⬜ Planned refinement

- Resolve active projects automatically.
- Capture important session changes and checkpoints.
- Persist the next safe action before shutdown or context exhaustion.

### 9. Distribution and publication — 🟡 Release candidate

Completed:

- [x] Build and validate wheel/sdist artifacts.
- [x] Install the wheel in clean environments on Ubuntu, Windows and macOS.
- [x] Run installed CLI smoke tests outside the source checkout.
- [x] Validate actual installed v0.2.0 → candidate upgrade on all three operating systems.
- [x] Prepare `CHANGELOG.md`, upgrade/rollback and release-operator documentation in PR #54.
- [x] Add release artifact SHA-256 generation/verification in PR #54.
- [x] Add a non-publishing tag workflow for exact-tag artifact validation in PR #54.

Remaining external publication work:

- [ ] Merge the fully green v0.3.0 release candidate.
- [ ] Tag the validated merge commit as `v0.3.0` and validate its retained artifact bundle.
- [ ] Create the GitHub Release with the exact wheel, sdist and `SHA256SUMS`.
- [ ] Publish the exact validated wheel/sdist to PyPI after secure publication/trust configuration is confirmed.
- [ ] Prepare/submit MCP Registry metadata after public release URLs are stable.

## Final product validation

- [x] Actual installed v0.2.0 → v0.3.0 candidate upgrade with existing data preserved.
- [x] Clean wheel installation on Ubuntu, Windows and macOS.
- [x] Safe multi-client configuration and rollback foundation.
- [x] SQLite local-first storage and deterministic connection lifecycle.
- [x] Owner/project isolation.
- [x] Runtime sanitization and poisoned-memory resistance.
- [x] Selective deletion and confirmed retention execution.
- [x] WAL-safe verified local backup and SHA-256 manifests.
- [x] Health and integrity diagnostics.
- [x] Confirmed two-phase restore and automatic rollback foundation.
- [x] Versioned SQLite migrations plus explicit installed upgrade lifecycle.
- [x] SQLite-first packaging with optional remote extras.
- [x] Core CI on Ubuntu, Windows and macOS across Python 3.11–3.13.
- [x] Wheel/sdist metadata and clean-install validation.
- [x] Centralized validated Settings foundation and safe legacy alias transition.
- [x] Git-grounded stale-memory classification foundation.
- [x] Deployment-target guardrails and regression evaluation.
- [x] Galaxy knowledge view.
- [x] Teams, roles and remote collaboration excluded from scope.
- [ ] Complete automatic continuation refinement.
- [ ] Persistent symbol history and full impact-analysis refinement.
- [ ] Complete operational dashboard refinement.
- [ ] GitHub Release/PyPI/MCP Registry publication.

## Recommended implementation order

1. Finish and validate PR #54 as the exact v0.3.0 release candidate.
2. Merge the green candidate and tag that exact merge commit `v0.3.0`.
3. Validate the tag-built wheel/sdist/`SHA256SUMS` bundle.
4. Publish the exact validated artifacts to GitHub Release and PyPI once secure publication configuration is confirmed.
5. Prepare/submit MCP Registry metadata.
6. Resume non-blocking product refinements: dashboard operations, automatic continuation and persistent symbol history.
