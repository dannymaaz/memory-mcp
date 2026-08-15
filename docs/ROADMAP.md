# Persistent Memory MCP delivery roadmap

This roadmap reflects merged work through PR #39. Persistent Memory MCP is a local-first personal application: one local installation, one private localhost dashboard and no shared workspace or multi-user role model.

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

Remaining release work:

- clean wheel/sdist installation validation;
- upgrade/uninstall validation against released packages.

### Local storage and isolation — ✅ Complete

- SQLite storage with WAL, foreign keys and scoped operations.
- Owner/project isolation on runtime reads and writes.
- Optional self-managed Supabase/PostgreSQL adapters.
- Import/export compatibility and packaged local schema.

### Security and retention — ✅ Complete

- Secret redaction, including nested dictionaries, lists and tuples.
- Stored-instruction detection, sensitivity and expiry metadata.
- Scope-validated retention candidate selection.
- Two-phase selective deletion and retention execution from PR #26.
- Exact record previews, signed short-lived confirmation tokens and plan fingerprints.
- Rejection of altered, expired, cross-scope or reused plans.
- Exact ID deletion, pre-mutation revalidation and audit metadata without deleted content.

### Verified SQLite backup and health — ✅ Complete foundation

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
- confirmed deletion MCP workflow available as the safe maintenance foundation.

Remaining:

- explicit pagination cursors;
- operational summary cards for storage, staleness, verification and sensitivity;
- polished empty, loading and error states;
- safe maintenance controls for backup, restore and confirmed deletion.

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

### 1. Verified backup creation and manifests — ✅ Complete foundation

- [x] Consistent WAL-safe SQLite backup — PR #29 / issue #28.
- [x] Integrity validation and bounded metadata — PR #29.
- [x] Versioned SHA-256 manifest and tamper verification — PR #35 / issue #31.

### 2. Database health and integrity — ✅ Complete foundation

PR #39 / issue #32 delivered:

- [x] `memory-mcp health`.
- [x] Bounded `quick_check` and optional full `integrity_check`.
- [x] Foreign-key and expected-index validation.
- [x] Database/WAL/SHM size, schema version and available disk space.
- [x] Latest verified backup discovery without memory contents.
- [x] `maintenance_ready` status requiring both healthy structure and a verified backup.

### 3. Two-phase verified restore — ⬜ Planned

Tracked by issue #33.

- Validate checksum, integrity, schema compatibility and available space.
- Produce an exact restore preview before mutation.
- Require explicit confirmation bound to the unchanged plan.
- Create a fresh verified backup of the active database before replacement.
- Replace the active database safely and recover from interrupted failures.

### 4. Versioned SQLite migrations — ⬜ Planned

Tracked by issue #34.

- Add `schema_migrations` tracking.
- Package ordered SQLite migration files.
- Record and validate migration checksums.
- Execute migrations transactionally.
- Require verified backup before irreversible migrations.
- Validate upgrade from the current 0.2.0 schema.

### 5. Configuration and package cleanup — ✅ Complete foundation

PR #30 aligned installation and runtime behavior with the local-first product direction:

- SQLite is the explicit default for new/runtime configuration when no backend is supplied;
- `MEMORY_BACKEND` is canonical while the historical `MEMORY_STORAGE_BACKEND` alias remains temporarily accepted during migration;
- Supabase/PostgreSQL drivers are optional package extras rather than core dependencies;
- the core package, lint, tests and evaluation regressions pass on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13;
- dependency audit validates both the core path and optional remote extras.

Remaining architectural cleanup:

- centralize configuration in one Settings object — issue #37;
- add a formal deprecation path for the legacy backend alias — issue #37;
- validate built wheel/sdist artifacts in clean environments — issue #38.

### 6. Dashboard completion — ⬜ Planned

- Add pagination, summary cards and accessible maintenance workflows.
- Surface backup health, last verified backup and database size.
- Integrate confirmed deletion and restore previews without bypassing safety gates.

### 7. Automatic continuation completion — ⬜ Planned

- Resolve active projects automatically.
- Capture important session changes and checkpoints.
- Persist the next safe action before shutdown or context exhaustion.

### 8. Distribution and publication — ⬜ Planned

- Build and validate wheel and sdist artifacts — issue #38.
- Install the wheel in a clean environment.
- Validate upgrade and uninstall workflows.
- Publish GitHub Release and PyPI artifacts with checksums.
- Prepare MCP Registry submission.

## Final product validation

- [ ] Clean local installation and upgrade from 0.2.0.
- [x] Safe multi-client configuration and rollback.
- [x] SQLite local-first storage.
- [x] Owner/project isolation.
- [x] Runtime sanitization and poisoned-memory resistance.
- [x] Selective deletion and confirmed retention execution.
- [x] WAL-safe verified local backup.
- [x] Versioned SHA-256 backup manifests and tamper detection.
- [x] Health and integrity diagnostics.
- [x] SQLite-first core packaging with optional remote extras.
- [x] Core CI on Ubuntu, Windows and macOS across Python 3.11–3.13.
- [ ] Confirmed two-phase restore and disaster recovery.
- [ ] Versioned SQLite migrations.
- [ ] Complete automatic continuation.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol history and full impact analysis.
- [x] Deployment-target guardrails and regression evaluation.
- [ ] Complete operational dashboard.
- [x] Galaxy knowledge view.
- [ ] Release and registry publication.
- [x] Teams, roles and remote collaboration excluded from scope.
