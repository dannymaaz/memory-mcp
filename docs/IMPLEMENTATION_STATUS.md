# Persistent Memory MCP implementation status

Last reconciled after merged PR #35 and PR #30. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

Persistent Memory MCP provides a strong local-first technical foundation for durable project memory: private SQLite storage, safe client installation, token-efficient context construction, owner/project isolation, hybrid search, persisted embeddings, session lifecycle management, Git-grounded verification, code intelligence, duplicate and contradiction analysis, deployment safety, evaluation tooling, a localhost-only dashboard, Galaxy visualization and confirmed destructive operations.

The first v0.3.0 data-safety and packaging milestones are now implemented. PR #29 added consistent WAL-safe SQLite backups with integrity validation, PR #35 added versioned SHA-256 manifests and independent tamper verification, and PR #30 aligned runtime/package defaults with the local-first product while validating the core suite across Ubuntu, Windows and macOS on Python 3.11–3.13. The remaining release blockers are health/integrity diagnostics, confirmed restore, versioned local migrations, wheel/sdist clean-install validation and the still-partial continuation/dashboard work.

## Capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and client onboarding | Complete foundation | PR #1, PR #4 | Release publication and broader upgrade validation |
| Security and isolation | Complete foundation | PR #2, PR #11, PR #20 | Continue adversarial coverage |
| SQLite local-first storage | Complete | PR #3 | Versioned migrations and recovery validation |
| Verified SQLite backup | Complete foundation | PR #29 | User-facing maintenance integration and recovery workflows |
| SHA-256 backup manifests | Complete | PR #35 | May later add stronger signing/rotation policies if needed |
| Database health and integrity | Planned | Issue #32 | Full implementation |
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
| Centralized Settings/deprecation cleanup | Partial | PR #30 foundation | Extract one Settings object and formally deprecate the legacy backend alias |
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

Confirmed deletion, verified backup, manifest verification and local-first package defaults are complete foundations. Automatic continuation, persistent symbol evolution and centralized Settings remain partial.

## Definition of done for v0.3.0

The Data Safety and Recovery release additionally requires:

- `memory-mcp health` and SQLite integrity diagnostics;
- two-phase verified restore with pre-restore backup;
- versioned and checksum-validated SQLite migrations;
- wheel/sdist build and clean-install validation;
- upgrade validation from 0.2.0;
- synchronized README, ROADMAP, implementation status and Notion records;
- release notes, rollback instructions, GitHub Release and PyPI validation.

Already completed for v0.3.0:

- SQLite-first package configuration with optional remote dependencies;
- Ubuntu, Windows and macOS critical-path CI on Python 3.11–3.13;
- verified SQLite backup and SHA-256 manifest foundations.

## Recommended implementation order

1. Implement health and integrity diagnostics — issue #32.
2. Implement two-phase verified restore — issue #33.
3. Implement versioned SQLite migrations — issue #34.
4. Build/test wheel and sdist artifacts and validate a clean install/upgrade from 0.2.0.
5. Complete dashboard pagination, health cards and safe maintenance actions.
6. Complete automatic project resolution and continuation checkpoints.
7. Persist and enrich the symbol graph across revisions.
8. Finish centralized Settings/deprecation cleanup, release notes and publish v0.3.0.
