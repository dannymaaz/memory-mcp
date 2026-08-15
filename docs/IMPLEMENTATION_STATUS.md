# Persistent Memory MCP implementation status

Last reconciled after merged PR #46 and PR #45. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

Persistent Memory MCP provides a strong local-first technical foundation for durable project memory: private SQLite storage, safe client installation, token-efficient context construction, owner/project isolation, hybrid search, persisted embeddings, session lifecycle management, Git-grounded verification, code intelligence, duplicate and contradiction analysis, deployment safety, evaluation tooling, a localhost-only dashboard, Galaxy visualization and confirmed destructive operations.

The v0.3.0 Data Safety and Recovery foundation is now implemented end to end: WAL-safe verified backups (PR #29), versioned SHA-256 manifests (PR #35), read-only SQLite health diagnostics (PR #39), two-phase verified restore with rollback and cross-platform hardening (PR #43 + PR #46), versioned checksum-verified local migrations with a v0.2 data-preservation regression (PR #45), SQLite-first packaging and optional remote extras (PR #30), and real wheel/sdist clean-install validation on Ubuntu, Windows and macOS (PR #41).

The remaining release work is no longer basic recovery. The active priorities are centralized Settings/deprecation cleanup (Issue #37 / PR #47), released-package upgrade/uninstall/rollback validation from 0.2.0, and final publication/registry preparation.

## Capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and client onboarding | Complete foundation | PR #1, PR #4, PR #39, PR #41 | Released-upgrade/uninstall validation |
| Security and isolation | Complete foundation | PR #2, PR #11, PR #20 | Continue adversarial coverage |
| SQLite local-first storage | Complete | PR #3, PR #45 | Future migrations must continue the new versioned contract |
| Verified SQLite backup | Complete foundation | PR #29 | Dashboard/CLI backup creation UX may be added later |
| SHA-256 backup manifests | Complete | PR #35 | May later add stronger signing/rotation policies if needed |
| Database health and integrity | Complete foundation | PR #39 | Dashboard health UX and future repair workflows |
| Confirmed two-phase restore | Complete foundation | PR #43, PR #46 | Dashboard restore UX may consume the existing safety contract later |
| Versioned SQLite migrations | Complete foundation | PR #45 | Validate released-package upgrade lifecycle, then add future numbered migrations as needed |
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
| SQLite-first packaging and cross-platform CI | Complete foundation | PR #30 | Released-upgrade validation |
| Release artifact validation | Complete | PR #41 | Upgrade/uninstall validation against an installed 0.2.0 environment |
| Centralized Settings/deprecation cleanup | Partial | PR #30 foundation; PR #47 draft | Finish critical caller migration and deprecation path |
| Teams and remote collaborative dashboard | Out of scope | PR #23 closed; issue #22 not planned | No implementation planned |
| Distribution and MCP Registry | Partial | PR #41 foundation | Final release publication and registry submission |

## Verified backup contract

PR #29 added a dedicated maintenance package and `BackupService` contract.

A successful backup:

- uses SQLite's backup API instead of copying the active file;
- remains consistent while WAL mode is active;
- refuses same-path destinations and pre-existing targets;
- writes through a temporary file and removes incomplete output on failure;
- validates the completed database with `PRAGMA integrity_check`;
- returns sizes, SQLite/schema versions and bounded table counts without exposing stored memory values.

PR #35 added a versioned JSON sidecar for successful backups containing bounded structural metadata and SHA-256 verification while intentionally excluding stored memory values and the source database path.

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

## Verified restore contract

PR #43 introduced the two-phase restore workflow and PR #46 completed its cross-platform revalidation model.

The restore flow:

1. `plan_memory_restore` verifies the selected backup manifest, SHA-256, SQLite integrity, schema compatibility and disk headroom without mutating the active database.
2. The plan contains a short-lived HMAC-bound confirmation token and a fingerprint of the exact operation.
3. `execute_memory_restore` rejects changed, expired, invalid or reused plans.
4. Immediately before replacement, the active database receives a fresh verified safety backup.
5. Active logical SQLite state is revalidated through a consistent WAL-aware snapshot fingerprint. Filesystem `mtime` and size remain diagnostic metadata rather than semantic drift signals.
6. WAL checkpoints must complete. WAL/SHM sidecar cleanup uses bounded retries for transient OS handle release and fails closed on persistent locks.
7. The verified restore source is copied to a same-directory temporary file, rechecked and atomically replaced.
8. Post-restore SHA-256, integrity and schema validation are mandatory.
9. If post-replacement validation fails, the verified safety backup is restored automatically and validated.

Quality run #188 passed the full Ubuntu/Windows/macOS Python 3.11–3.13 matrix, all three release-artifact clean-install jobs and dependency audit after the final cross-platform fix.

## Versioned migration contract

PR #45 established the first formal SQLite migration lifecycle.

The migration service:

- exposes a read-only preview that does not create `schema_migrations` or mutate the database;
- requires positive unique ordered versions;
- rejects migration SQL that attempts to manage its own transaction;
- validates `PRAGMA quick_check` and the required v0.2 core tables before any write;
- rejects database schema versions newer than the supported migration set;
- rejects migration history ahead of `PRAGMA user_version`;
- rejects `user_version` claims for which the corresponding recorded history is missing;
- records and verifies migration names and SHA-256 checksums;
- creates a verified pre-migration backup before any pending migration is applied;
- executes each migration transactionally and records it only after success;
- leaves completed prior migrations intact while rolling back a failing migration's own transaction;
- is idempotent once the database is current.

The first packaged migration establishes the explicit v0.3 schema baseline. Tests construct the existing v0.2 schema, insert existing task data, execute the migration and prove the data is preserved. Quality run #190 passed Ubuntu, Windows and macOS on Python 3.11–3.13, all three real wheel/sdist clean-install jobs and dependency audit.

This is a schema/data upgrade regression. A separate release-lifecycle check is still required to install the actual 0.2.0 package, upgrade it with the candidate v0.3.0 wheel, verify behavior, then validate uninstall/rollback instructions.

## SQLite-first packaging contract

PR #30 aligned installation and runtime behavior without forcing a breaking rewrite of legacy adapter helpers:

- new/default runtime configuration falls back to SQLite when no backend variable is present;
- `MEMORY_BACKEND` is the canonical variable for new configuration;
- the historical `MEMORY_STORAGE_BACKEND` alias is still accepted temporarily by the runtime migration path;
- Supabase and PostgreSQL drivers moved to optional package extras instead of every SQLite installation;
- the core package, lint, tests and evaluation regressions run on Ubuntu, Windows and macOS across Python 3.11, 3.12 and 3.13;
- dependency audit also installs and checks the optional remote extras.

The low-level legacy `normalize_backend(None)` contract remains preserved while critical callers migrate to the centralized Settings contract in PR #47.

## Centralized Settings work

Issue #37 is active through draft PR #47.

The current Settings slice introduces:

- immutable Pydantic-backed `RuntimeSettings`;
- SQLite as the Settings default;
- `MEMORY_BACKEND` as canonical and `MEMORY_STORAGE_BACKEND` as a deprecated transition alias;
- a `FutureWarning` for the legacy alias;
- fail-closed behavior when canonical and legacy backend variables conflict;
- validated SQLite path, owner ID, remote configuration, logging, interface, privacy, ignore-pattern and retention settings;
- `SecretStr` masking for Supabase, PostgreSQL and confirmation secrets;
- the existing `OWNER_ID` fallback for restore/deletion confirmation compatibility;
- Settings-based storage client selection in `src/utils/db.py`;
- Settings injection support at the verified restore integration boundary without changing public MCP tool names.

The first PR #47 matrix is green. The issue remains partial until critical direct environment reads are migrated and the final deprecation contract is documented and revalidated against current `main`.

## Release artifact validation contract

PR #41 validates the artifacts users would actually install rather than relying only on editable development installs.

Release CI now:

- builds wheel and sdist with `python -m build`;
- runs `twine check` on both artifacts;
- checks that required runtime and SQLite schema assets are packaged;
- installs the wheel in a fresh virtual environment outside the repository checkout;
- verifies the `memory-mcp` entrypoint;
- smoke-tests installed `init`, `doctor`, `status` and `health` commands;
- confirms the local SQLite database and client configuration are created from the built wheel;
- runs this artifact validation on Ubuntu, Windows and macOS.

The clean Windows install exposed a real CP1252 redirected-console bug; PR #41 replaced Unicode status glyphs with portable `[ok]`, `[error]` and `[skip]` markers and modernized license metadata.

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

Confirmed deletion, verified backup, manifest verification, health diagnostics, verified restore, versioned migrations, local-first package defaults and real artifact validation are complete foundations. Automatic continuation, persistent symbol evolution and centralized Settings remain partial.

## Definition of done for v0.3.0

Already completed for the v0.3.0 safety foundation:

- SQLite-first package configuration with optional remote dependencies;
- Ubuntu, Windows and macOS critical-path CI on Python 3.11–3.13;
- verified SQLite backup and SHA-256 manifest foundations;
- read-only SQLite health and maintenance-readiness diagnostics;
- two-phase verified restore with pre-restore safety backup and rollback;
- cross-platform WAL-aware restore drift/handle behavior;
- versioned checksum-validated SQLite migrations;
- v0.2-shaped schema/data migration regression with preserved existing data;
- wheel/sdist build, metadata validation and clean wheel installation on Ubuntu, Windows and macOS.

The release still requires:

- completion of centralized Settings/deprecation cleanup — issue #37 / PR #47;
- released-package upgrade/uninstall/rollback validation from an actual installed 0.2.0 environment;
- synchronized release notes and rollback instructions;
- GitHub Release and PyPI publication validation;
- MCP Registry preparation.

## Recommended implementation order

1. Finish centralized Settings/deprecation cleanup — issue #37 / PR #47.
2. Validate actual package upgrade/uninstall/rollback from 0.2.0 to the v0.3.0 candidate.
3. Complete dashboard pagination, health cards and safe maintenance actions.
4. Complete automatic project resolution and continuation checkpoints.
5. Persist and enrich the symbol graph across revisions.
6. Finalize release notes, rollback instructions and publish v0.3.0.
7. Prepare MCP Registry submission.
