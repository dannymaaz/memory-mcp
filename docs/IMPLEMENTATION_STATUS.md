# Persistent Memory MCP implementation status

Last reconciled after merged PR #52 plus the v0.3.0 release candidate in PR #54. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

Persistent Memory MCP now has a release-grade local data-safety foundation: private SQLite storage, owner/project isolation, WAL-safe verified backup, SHA-256 manifests, read-only health diagnostics, confirmed two-phase restore with automatic rollback, versioned backup-first migrations, explicit installed migration tooling, a fail-closed startup migration guard, deterministic SQLite connection lifecycle, validated runtime Settings and cross-platform release-artifact testing.

The release lifecycle has also moved beyond schema-only simulation. PR #51 installs the pinned historical 0.2.0 package in a clean environment, creates real project/task data, installs the candidate, verifies startup refuses the pending schema, applies the explicit migration with a verified backup and proves the original data survives on Ubuntu, Windows and macOS. PR #52 revalidates that lifecycle after making context-managed SQLite handles close deterministically.

PR #54 is the v0.3.0 release candidate. It bumps package metadata to 0.3.0, adds release notes and backup-first upgrade/rollback instructions, validates 0.3.0 metadata in built artifacts, generates/verifies SHA-256 manifests and adds a non-publishing tag workflow that rebuilds and revalidates the exact tagged commit before retaining the release bundle.

The remaining v0.3.0 work is external publication: finish candidate CI, merge/tag the exact validated commit, validate the tag bundle, then create the GitHub Release and publish the same wheel/sdist to PyPI once secure publication configuration is confirmed. MCP Registry preparation follows stable public release URLs.

## Capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and client onboarding | Complete foundation | PR #1, PR #4, PR #39, PR #41, PR #51 | External v0.3 release publication |
| Security and isolation | Complete foundation | PR #2, PR #11, PR #20 | Continue adversarial coverage |
| SQLite local-first storage | Complete | PR #3, PR #45, PR #51, PR #52 | Future numbered migrations continue the contract |
| Verified SQLite backup | Complete foundation | PR #29 | Dashboard backup UX may be added later |
| SHA-256 backup manifests | Complete | PR #35 | Stronger signing/rotation is optional future work |
| Database health and integrity | Complete foundation | PR #39 | Dashboard health UX and future repair workflows |
| Confirmed two-phase restore | Complete foundation | PR #43, PR #46 | Dashboard restore UX may consume the safety contract later |
| Versioned SQLite migrations | Complete | PR #45, PR #51 | Future schema changes add new numbered migrations |
| Installed v0.2.0 upgrade lifecycle | Complete | PR #51 / Quality #200; PR #52 / Quality #202 | Final tagged artifact revalidation in release workflow |
| Runtime Settings foundation | Complete foundation | PR #47, PR #51 | Provider/subsystem-specific env reads remain incremental refactor debt |
| Deterministic SQLite connection lifecycle | Complete | PR #52 | None for current local adapter contract |
| Token-efficient context | Complete | PR #5 | Continue quality benchmarking |
| Hybrid search and embeddings | Complete foundation | PR #6, PR #12 | Background indexing and broader benchmarks |
| Automatic sessions | Partial | PR #7 | Automatic project resolution and complete continuation checkpoints |
| Git verification | Complete foundation | PR #8 | Richer rebase, rename and PR binding |
| Code intelligence | Partial | PR #9 | Persistent historical symbol tracking and richer links |
| Duplicate and contradiction intelligence | Complete | PR #13 | Broader domain-specific regression coverage |
| Deployment history and action risk | Complete | PR #14 | Broader deployment adapter coverage |
| Evaluation and provenance suite | Complete | PR #15 | Expand scenarios as features evolve |
| Local dashboard | Partial | PR #16 | Pagination, summary cards and maintenance UX |
| Galaxy knowledge view | Complete foundation | PR #17, PR #18 | Performance/usability refinement |
| Nested secret redaction | Complete | PR #20 | Continue adversarial coverage |
| Confirmed deletion and retention execution | Complete | PR #26 | Dashboard controls may consume the workflow later |
| SQLite-first packaging and cross-platform CI | Complete | PR #30, PR #41 | External release publication |
| v0.3.0 release candidate | In review | PR #54 | Full candidate CI, merge/tag and external publication |
| Teams and remote collaborative dashboard | Out of scope | PR #23 closed; issue #22 not planned | No implementation planned |
| GitHub Release / PyPI / MCP Registry | Planned publication | Issue #53 / PR #54 prep | Publish only exact validated artifacts |

## Verified backup contract

PR #29 added a dedicated maintenance package and `BackupService` contract. A successful backup:

- uses SQLite's backup API instead of copying the active file;
- remains consistent while WAL mode is active;
- refuses same-path destinations and pre-existing targets;
- writes through a temporary file and removes incomplete output on failure;
- validates the completed database with `PRAGMA integrity_check`;
- returns sizes, SQLite/schema versions and bounded table counts without exposing stored memory values.

PR #35 adds a versioned JSON sidecar with SHA-256 verification, package/SQLite/schema metadata, size, integrity and bounded table counts while intentionally excluding stored memory values and the source database path.

## SQLite health contract

PR #39 added a read-only `HealthService` and `memory-mcp health` command. The report:

- always runs bounded `PRAGMA quick_check`;
- can run full `PRAGMA integrity_check` with `--full`;
- reports foreign-key violations without row contents;
- verifies expected operational indexes;
- reports SQLite/schema version, journal mode, DB/WAL/SHM sizes and free disk space;
- can discover the latest valid SHA-256 backup through `--backup-dir`;
- counts invalid backup manifests without exposing their contents;
- returns `maintenance_ready=true` only when structure is healthy and a verified backup is available;
- avoids stored memory values and the absolute active database path in normal CLI output.

## Verified restore contract

PR #43 introduced two-phase restore; PR #46 completed cross-platform revalidation.

1. `plan_memory_restore` verifies backup manifest, SHA-256, integrity, schema compatibility and disk headroom without mutating the active database.
2. The plan receives a short-lived HMAC-bound confirmation token and exact operation fingerprint.
3. `execute_memory_restore` rejects changed, expired, invalid or reused plans.
4. The active database receives a fresh verified safety backup immediately before replacement.
5. Logical SQLite state is revalidated through a consistent WAL-aware snapshot fingerprint; filesystem `mtime`/size are diagnostic rather than semantic drift signals.
6. WAL checkpoints must complete; sidecar cleanup tolerates only bounded transient handle release and fails closed on persistent locks.
7. The restore source is copied to a same-directory temporary file, rechecked and atomically replaced.
8. Post-restore SHA-256, integrity and schema validation are mandatory.
9. Failed post-replacement validation automatically restores and validates the safety backup.

Quality #188 passed the full Ubuntu/Windows/macOS Python 3.11–3.13 matrix, all release-artifact clean installs and dependency audit after the final restore fix.

## Versioned migration and installed-upgrade contract

PR #45 established the migration engine. PR #51 integrated it into the user/runtime lifecycle.

The migration service:

- exposes a read-only preview;
- requires positive unique ordered versions;
- rejects migration SQL that manages its own transaction;
- validates `quick_check` and required v0.2 core tables before writes;
- rejects future schema versions and inconsistent `user_version`/history states;
- records/validates migration names and SHA-256 checksums;
- creates a verified pre-migration backup before pending migrations;
- executes each migration transactionally and records it only after success;
- is idempotent once current.

The installed lifecycle adds:

- `memory-mcp-migrate` as the explicit user command;
- read-only preview by default;
- mutation only with `--apply --yes`;
- startup migration-state inspection before server import/start;
- fail-closed startup if an existing SQLite database is stale;
- no startup automigration;
- current-schema bootstrap only for a database file that was genuinely new and still empty;
- refusal to bootstrap any database containing user rows, migration history or non-zero schema version.

Quality #200 validates the real package path: CI builds/installs the pinned v0.2.0 commit `e502f747…`, creates actual project/task data, installs the candidate, confirms the stale schema is blocked, runs explicit backup-first migration and verifies data preservation on Ubuntu, Windows and macOS.

## Deterministic SQLite connection lifecycle

PR #52 corrects a subtle Python `sqlite3` assumption in the local adapter. Native connection context management commits/rolls back but does not itself guarantee `close()`.

`SQLiteStorage.connect()` now returns a SQLite connection subtype through the supported `factory` hook. Its context exit:

1. executes native SQLite commit/rollback behavior;
2. always closes the connection in `finally`.

Success and exception-path regressions prove commit+close and rollback+close. Quality #202 revalidates the full Python/OS matrix, clean artifacts and historical installed upgrade lifecycle.

## SQLite-first packaging and RuntimeSettings

PR #30 makes SQLite the normal local path and moves Supabase/PostgreSQL drivers to optional extras.

PR #47 completed Issue #37's centralized Settings foundation:

- immutable Pydantic-backed `RuntimeSettings`;
- SQLite default;
- canonical `MEMORY_BACKEND`;
- transitional `MEMORY_STORAGE_BACKEND` with `FutureWarning`;
- fail-closed conflicting aliases;
- validated SQLite path, owner ID, remote configuration, logging, interface, privacy, ignore-pattern and retention settings;
- `SecretStr` masking for Supabase/PostgreSQL/confirmation secrets;
- existing `OWNER_ID` confirmation-secret fallback;
- Settings-based storage client resolution/injection and restore integration.

PR #51 also uses RuntimeSettings for startup backend/path and migration readiness. Specialized provider/subsystem environment variables remain valid incremental configuration inputs and are not a blocker for the v0.3.0 local product.

## Release artifact contract

PR #41 validates artifacts users actually install:

- `python -m build` wheel/sdist;
- `twine check`;
- required runtime/schema assets;
- clean wheel install outside the source checkout;
- installed entrypoint and CLI smoke tests on Ubuntu/Windows/macOS.

PR #51 adds the installed historical upgrade lifecycle on every release-artifact OS job.

PR #54 release candidate adds:

- package version `0.3.0` in metadata;
- editable-install version assertion;
- wheel filename/METADATA and sdist root version validation;
- generated/verified `SHA256SUMS` for wheel/sdist;
- `CHANGELOG.md`;
- `docs/UPGRADING.md` with backup-first upgrade/rollback;
- `docs/RELEASING.md` with GitHub Release, PyPI and MCP Registry gates;
- a tag workflow that requires `vX.Y.Z` to equal package version, rebuilds exact-tag artifacts, repeats clean install/historical upgrade checks, generates checksums and retains the bundle without automatically publishing it.

External publishing intentionally remains separate until trusted publication configuration and the exact tag bundle are verified.

## Confirmed deletion contract

PR #26 added:

- `plan_memory_deletion` for dry-run exact IDs/counts/fingerprint/expiry/signed confirmation;
- `execute_memory_deletion` for unchanged, scoped, unexpired and single-use confirmed plans.

Retention candidates use the same contract. Retention deletion never runs automatically at startup. Current records are revalidated immediately before mutation, unrelated projects remain intact and audit events store operation metadata/counts without deleted content.

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

Supabase/PostgreSQL adapters remain optional advanced self-managed persistence modes without changing the local product direction.

## Definition of done for the technical core

The local technical core has complete foundations for sanitization/scoping, deletion, backup, health, restore, versioned migration, installed upgrade, cross-platform package validation, deployment safety and regression evaluation.

Non-blocking product refinements remain partial:

- automatic project resolution/continuation checkpoints;
- persistent symbol evolution/history;
- dashboard pagination, summary cards and maintenance controls;
- broader search/provider benchmarks.

## Definition of done for v0.3.0

Completed before the release candidate:

- [x] SQLite-first package configuration with optional remote dependencies.
- [x] Ubuntu/Windows/macOS critical-path CI on Python 3.11–3.13.
- [x] Verified SQLite backup and SHA-256 manifest foundations.
- [x] Read-only SQLite health and maintenance-readiness diagnostics.
- [x] Two-phase verified restore with safety backup and rollback.
- [x] Cross-platform WAL-aware restore behavior.
- [x] Versioned checksum-validated SQLite migrations.
- [x] Explicit migration CLI and fail-closed startup guard.
- [x] Real installed v0.2.0 → candidate upgrade with existing data preserved on all three operating systems.
- [x] Deterministic context-managed SQLite connection close semantics.
- [x] Centralized validated Settings foundation.
- [x] Wheel/sdist build, metadata and clean-install validation on all three operating systems.

Prepared in PR #54:

- [x] Package metadata bumped to 0.3.0.
- [x] Release notes and backup-first upgrade/rollback instructions.
- [x] SHA-256 artifact manifest generation/verification.
- [x] Exact-tag non-publishing release bundle workflow.
- [x] README/ROADMAP/IMPLEMENTATION_STATUS release reconciliation.

Remaining publication gate:

- [ ] PR #54 exact head passes complete Quality CI.
- [ ] Merge the validated candidate and create `v0.3.0` tag from that exact merge commit.
- [ ] Tag workflow succeeds and retained wheel/sdist/`SHA256SUMS` bundle is verified.
- [ ] Create final GitHub Release with exact validated artifacts.
- [ ] Publish the same wheel/sdist to PyPI after secure publication configuration is confirmed.
- [ ] Prepare/submit MCP Registry metadata after public URLs are stable.

## Recommended implementation order

1. Finish PR #54 Quality CI and fix any release-candidate regression.
2. Merge the exact green candidate and tag its merge commit `v0.3.0`.
3. Validate the tag-generated artifact/checksum bundle.
4. Publish the exact bundle to GitHub Release and PyPI once publication trust/config is confirmed.
5. Prepare/submit MCP Registry metadata.
6. Resume dashboard, continuation and symbol-history refinements as post-v0.3 work.
