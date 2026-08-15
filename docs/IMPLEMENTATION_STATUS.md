# Persistent Memory MCP implementation status

Last reconciled after merged PR #39. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

Persistent Memory MCP provides a strong local-first technical foundation for durable project memory: private SQLite storage, safe client installation, token-efficient context construction, owner/project isolation, hybrid search, persisted embeddings, session lifecycle management, Git-grounded verification, code intelligence, duplicate and contradiction analysis, deployment safety, evaluation tooling, a localhost-only dashboard, Galaxy visualization and confirmed destructive operations.

The v0.3.0 Data Safety and Recovery track now includes WAL-safe verified backups (PR #29), versioned SHA-256 manifests (PR #35), SQLite-first packaging and cross-platform CI (PR #30), and read-only SQLite health/maintenance-readiness diagnostics (PR #39). The remaining release blockers are confirmed restore, versioned local migrations, wheel/sdist clean-install validation and the still-partial continuation/dashboard work.

## Capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and client onboarding | Complete foundation | PR #1, PR #4, PR #39 | Release publication and broader upgrade validation |
| Security and isolation | Complete foundation | PR #2, PR #11, PR #20 | Continue adversarial coverage |
| SQLite local-first storage | Complete | PR #3 | Versioned migrations and recovery validation |
| Verified SQLite backup | Complete foundation | PR #29 | Dashboard/CLI backup creation UX may be added later |
| SHA-256 backup manifests | Complete | PR #35 | May later add stronger signing/rotation policies if needed |
| Database health and integrity | Complete foundation | PR #39 | Dashboard health UX and future repair workflows |
| Confirmed two-phase restore | Planned | Issue #33 | Full implementation |
| Versioned SQLite migrations | Planned | Issue #34 | Full implementation and 0.2.0 upgrade validation |
| Token-efficient context | Complete | PR #5 | Continue quality benchmarking |
| Hybrid search and embeddings | Complete foundation | PR #6, PR #12 | Background indexing and broader benchmarks |
| Automatic sessions | Partial | PR #7 | Automatic project resolution and complete continuation checkpoints |
| Git verification | Complete foundation | PR #8 | Richer rebase, rename and PR binding |
| Code intelligence | Partial | PR #9 | Persistent historical symbol tracking and richer links |
| Duplicate and contradiction intelligence | Complete | PR #13 | Broader domain-specific regression coverage |
| Deployment history and action risk | Complete | PR #14 | Broader deployment adapter coverage |
| Evaluation and provenance suite | Complete | PR #15 | Expand scenarios as features evolve |
| Local dashboard | Partial | PR #16 | Pagination, summary cards and maintenance UX |
| Galaxy knowledge view | Complete foundation | PR #17, PR #18 | Performance and usability refinement |
| Nested secret redaction | Complete | PR #20 | Continue adversarial coverage |
| Confirmed deletion and retention execution | Complete | PR #26 | Dashboard controls may consume the workflow later |
| SQLite-first packaging and cross-platform CI | Complete foundation | PR #30 | Wheel/sdist clean-install and released-upgrade validation |
| Centralized Settings/deprecation cleanup | Partial | PR #30 foundation; Issue #37 | Extract one Settings object and formally deprecate the legacy backend alias |
| Release artifact validation | Planned | Issue #38 | Wheel/sdist build, clean install and smoke tests |
| Teams and remote collaborative dashboard | Out of scope | PR #23 closed; issue #22 not planned | No implementation planned |
| Distribution and MCP Registry | Planned | Future release work | Release automation and publication |

## Verified backup contract

PR #29 added a dedicated maintenance package and `BackupService` contract.

A successful backup:

- uses SQLite's backup API instead of copying the active file;
- remains consistent while WAL mode is active;
- refuses same-path destinations and pre-existing targets;
- writes through a temporary file and removes incomplete output on failure;
- validates the completed database with `PRAGMA integrity_check`;
- returns sizes, SQLite/schema versions and bounded table counts without exposing stored memory values.

Quality workflow #149 passed compilation, Ruff, Pytest, evaluation regressions and dependency audit across Python 3.11, 3.12 and 3.13.

## Backup manifest contract

PR #35 added a versioned JSON sidecar for successful backups.

The manifest records:

- manifest format and package version;
- UTC creation time;
- backup filename and size;
- SHA-256 digest;
- SQLite and schema versions;
- integrity result;
- bounded table counts.

It intentionally excludes stored memory values and the source database path. Verification rejects malformed manifests, unsupported versions, filename/size mismatch and SHA-256 mismatch. Quality workflow #152 passed across Python 3.11, 3.12 and 3.13.

## SQLite health contract

PR #39 added a read-only `HealthService` and `memory-mcp health` command.

The health report:

- always runs a bounded `PRAGMA quick_check`;
- can run full `PRAGMA integrity_check` with `--full`;
- reports foreign-key violations without returning row contents;
- verifies expected operational indexes;
- reports SQLite/schema version, journal mode, DB/WAL/SHM sizes and free disk space;
- can discover the latest valid SHA-256 backup through `--backup-dir`;
- counts invalid backup manifests without exposing their contents;
- returns `maintenance_ready=true` only when the database is structurally healthy and a verified backup is available;
- avoids returning stored memory values or the absolute active database path in normal CLI output.

Quality workflow #165 passed on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13 plus dependency audit.

## SQLite-first packaging contract

PR #30 aligned installation and runtime behavior without forcing a breaking rewrite of legacy adapter helpers:

- new/default runtime configuration falls back to SQLite when no backend variable is present;
- `MEMORY_BACKEND` is the canonical variable for new configuration;
- the historical `MEMORY_STORAGE_BACKEND` alias is still accepted temporarily by the runtime migration path;
- Supabase and PostgreSQL drivers moved to optional package extras instead of every SQLite installation;
- the core package, lint, tests and evaluation regressions run on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13;
- dependency audit also installs and checks the optional remote extras.

The generic legacy `normalize_backend(None)` contract is intentionally preserved until the planned centralized Settings migration, avoiding an unrelated breaking change inside the packaging PR.

## Confirmed deletion contract

PR #26 added two MCP tools:

- `plan_memory_deletion` creates a dry-run preview with exact IDs, counts, fingerprint, expiry and signed confirmation token.
- `execute_memory_deletion` validates the unchanged plan, active owner/project scope, expiry and single-use confirmation before deleting exact IDs.

The same contract supports retention candidates. Retention deletion never runs automatically at startup. Current records are revalidated immediately before mutation, unrelated projects are preserved, and audit events store operation metadata and counts without copying deleted content.

## Product scope

Persistent Memory MCP is designed around:

- one personal installation;
- local SQLite as the default persistence backend;
- localhost-only dashboard access;
- project and owner isolation inside the installation;
- no workspace invitations or team memberships;
- no owner/admin/member/reader hierarchy;
- no public remote collaborative dashboard;
- no billing or organization-management surface.

Supabase and PostgreSQL adapters remain available as optional advanced self-managed persistence modes, but they do not change the local product direction.

## Definition of done for the technical core

The technical core is substantially complete when:

- every memory write is sanitized and scoped;
- reads and writes enforce owner/project boundaries;
- selective deletion and retention execution are exposed safely;
- embeddings can be persisted, refreshed and reindexed;
- sessions automatically identify projects and save continuation checkpoints;
- symbol indexes persist across revisions;
- adversarial isolation, poisoned-memory and handoff tests pass.

Confirmed deletion, verified backup, manifest verification, health diagnostics and local-first package defaults are complete foundations. Automatic continuation, persistent symbol evolution and centralized Settings remain partial.

## Definition of done for v0.3.0

The Data Safety and Recovery release still requires:

- two-phase verified restore with pre-restore backup — issue #33;
- versioned and checksum-validated SQLite migrations — issue #34;
- wheel/sdist build and clean-install validation — issue #38;
- upgrade validation from 0.2.0;
- synchronized release notes and rollback instructions;
- GitHub Release and PyPI validation.

Already completed for v0.3.0:

- SQLite-first package configuration with optional remote dependencies;
- Ubuntu, Windows and macOS critical-path CI on Python 3.11–3.13;
- verified SQLite backup and SHA-256 manifest foundations;
- read-only SQLite health and maintenance-readiness diagnostics.

## Recommended implementation order

1. Implement two-phase verified restore — issue #33.
2. Implement versioned SQLite migrations — issue #34.
3. Build/test wheel and sdist artifacts and validate a clean install/upgrade from 0.2.0 — issue #38.
4. Complete dashboard pagination, health cards and safe maintenance actions.
5. Complete automatic project resolution and continuation checkpoints.
6. Persist and enrich the symbol graph across revisions.
7. Finish centralized Settings/deprecation cleanup — issue #37.
8. Finalize release notes and publish v0.3.0.
