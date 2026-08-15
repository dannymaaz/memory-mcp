# Persistent Memory MCP delivery roadmap

This roadmap reflects merged work through PR #46. Persistent Memory MCP is a local-first personal application: one local installation, one private localhost dashboard and no shared workspace or multi-user role model.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Product CLI and local onboarding — ✅ Complete foundation

- `memory-mcp` and `persistent-memory-mcp` command aliases.
- `init`, `doctor`, `status`, `health` and `serve` commands.
- Safe client configuration with backup, rollback and uninstall support.
- Ubuntu, Windows and macOS CI across Python 3.11–3.13.
- Wheel/sdist build and clean-install validation on Ubuntu, Windows and macOS.

Remaining release work:

- released-upgrade/uninstall validation against an existing 0.2.0 installation;
- final release publication and rollback documentation.

### Local storage and isolation — ✅ Complete

- SQLite storage with WAL, foreign keys and scoped operations.
- Owner/project isolation on runtime reads and writes.
- Optional self-managed Supabase/PostgreSQL adapters.
- Import/export compatibility and packaged local schema.
- Versioned local migration foundation with checksum tracking.

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

PR #45 added the first formal local migration framework:

- read-only migration preview;
- `schema_migrations` history recorded only during execution;
- stable ordered migration versions and SHA-256 checksums;
- future/inconsistent schema-history states are rejected;
- pending migrations require a verified pre-migration backup;
- each migration is transactional and recorded only after success;
- the v0.2 schema upgrade path is covered by a regression that preserves existing data.

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

Remaining:

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

PR #39 / issue #32 delivered:

- [x] `memory-mcp health`.
- [x] Bounded `quick_check` and optional full `integrity_check`.
- [x] Foreign-key and expected-index validation.
- [x] Database/WAL/SHM size, schema version and available disk space.
- [x] Latest verified backup discovery without memory contents.
- [x] `maintenance_ready` status requiring both healthy structure and a verified backup.

### 3. Two-phase verified restore — ✅ Complete

PR #43 / issue #33 delivered the restore contract; PR #46 completed cross-platform hardening.

- [x] Validate checksum, integrity, schema compatibility and available space.
- [x] Produce an exact restore preview before mutation.
- [x] Require explicit confirmation bound to the unchanged plan.
- [x] Create a fresh verified backup of the active database before replacement.
- [x] Use WAL-aware logical-state fingerprinting for drift detection.
- [x] Replace atomically and automatically rollback after failed post-restore validation.
- [x] Fail closed on busy checkpoints or persistent WAL/SHM locks.
- [x] Validate on Ubuntu, Windows and macOS across Python 3.11–3.13.

### 4. Versioned SQLite migrations — ✅ Complete foundation

PR #45 / issue #34 delivered:

- [x] `schema_migrations` tracking.
- [x] Ordered packaged migration modules.
- [x] SHA-256 migration checksums and altered-history detection.
- [x] Transactional migration execution.
- [x] Verified backup before applying pending migrations.
- [x] Future/inconsistent schema history rejection.
- [x] Upgrade regression from the current v0.2 schema with existing data preserved.
- [x] Wheel/sdist clean-install validation on Ubuntu, Windows and macOS.

### 5. Configuration and package cleanup — 🟡 Partial

PR #30 aligned installation and runtime behavior with the local-first product direction:

- SQLite is the explicit default for new/runtime configuration when no backend is supplied;
- `MEMORY_BACKEND` is canonical while the historical `MEMORY_STORAGE_BACKEND` alias remains temporarily accepted during migration;
- Supabase/PostgreSQL drivers are optional package extras rather than core dependencies;
- the core package, lint, tests and evaluation regressions pass on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13;
- dependency audit validates both the core path and optional remote extras.

PR #41 completed built-artifact validation:

- `python -m build` produces wheel and sdist;
- `twine check` validates package metadata;
- packaged SQLite/runtime assets are inspected directly;
- the wheel is installed in a clean environment outside the repository checkout;
- installed `init`, `doctor`, `status` and `health` commands are smoke-tested on Ubuntu, Windows and macOS;
- a real Windows redirected-console encoding bug was fixed with portable ASCII status markers.

PR #47 is the active Settings cleanup:

- one validated immutable RuntimeSettings contract;
- SQLite default in the Settings contract;
- canonical `MEMORY_BACKEND` plus bounded deprecation warning for `MEMORY_STORAGE_BACKEND`;
- fail-closed conflicting aliases;
- masked remote/confirmation secrets;
- incremental migration of runtime consumers without breaking MCP tool names.

Remaining architectural cleanup:

- finish migrating critical direct environment reads to RuntimeSettings;
- complete the documented deprecation path before removing legacy behavior.

### 6. Dashboard completion — ⬜ Planned

- Add pagination, summary cards and accessible maintenance workflows.
- Surface backup health, last verified backup and database size.
- Integrate confirmed deletion and restore previews without bypassing safety gates.

### 7. Automatic continuation completion — ⬜ Planned

- Resolve active projects automatically.
- Capture important session changes and checkpoints.
- Persist the next safe action before shutdown or context exhaustion.

### 8. Distribution and publication — 🟡 Partial

Completed:

- [x] Build and validate wheel and sdist artifacts — PR #41 / issue #38.
- [x] Install the wheel in clean environments on Ubuntu, Windows and macOS.
- [x] Run installed CLI smoke tests outside the source checkout.
- [x] Validate a v0.2-shaped SQLite database through the versioned migration path — PR #45.

Remaining:

- [ ] Validate released-package upgrade/uninstall/rollback behavior against an actual installed 0.2.0 package environment.
- [ ] Publish GitHub Release and PyPI artifacts with checksums.
- [ ] Prepare MCP Registry submission.

## Final product validation

- [ ] Released-package upgrade/uninstall/rollback from an existing 0.2.0 installation.
- [x] Clean wheel installation on Ubuntu, Windows and macOS.
- [x] Safe multi-client configuration and rollback foundation.
- [x] SQLite local-first storage.
- [x] Owner/project isolation.
- [x] Runtime sanitization and poisoned-memory resistance.
- [x] Selective deletion and confirmed retention execution.
- [x] WAL-safe verified local backup.
- [x] Versioned SHA-256 backup manifests and tamper detection.
- [x] Health and integrity diagnostics.
- [x] Confirmed two-phase restore and rollback foundation.
- [x] Versioned SQLite migrations and v0.2 schema/data upgrade regression.
- [x] SQLite-first core packaging with optional remote extras.
- [x] Core CI on Ubuntu, Windows and macOS across Python 3.11–3.13.
- [x] Wheel/sdist metadata and clean-install validation.
- [ ] Centralized Settings migration complete.
- [ ] Complete automatic continuation.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol history and full impact analysis.
- [x] Deployment-target guardrails and regression evaluation.
- [ ] Complete operational dashboard.
- [x] Galaxy knowledge view.
- [ ] Release and registry publication.
- [x] Teams, roles and remote collaboration excluded from scope.

## Recommended implementation order

1. Finish centralized Settings and legacy alias deprecation — issue #37 / PR #47.
2. Validate released-package upgrade/uninstall/rollback from an actual 0.2.0 installation.
3. Complete dashboard pagination, health cards and safe maintenance actions.
4. Complete automatic project resolution and continuation checkpoints.
5. Persist and enrich the symbol graph across revisions.
6. Finalize release notes, rollback instructions and publish v0.3.0.
7. Prepare MCP Registry submission.
