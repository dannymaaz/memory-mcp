# Persistent Memory MCP delivery roadmap

This roadmap reflects the repository state through PR #21 and the product-scope decision recorded after PR #23 was closed without merge. Persistent Memory MCP is a local-first personal application: one local installation, one private dashboard and no shared workspace or multi-user role model.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### PR #1 — Product CLI and multi-client onboarding — ✅ Complete

- Python distribution renamed to `persistent-memory-mcp`.
- `memory-mcp` and `persistent-memory-mcp` command aliases.
- `init`, `doctor`, `status` and `serve` commands.
- Configuration generation for supported MCP clients.
- Package, documentation and Python 3.11–3.13 CI foundation.

### PR #2 — Security, isolation and retention foundation — 🟡 Partial

Completed:

- Secret redaction primitives.
- Stored-instruction detection and untrusted-content metadata.
- Content-size limits, provenance normalization and TTL metadata.
- Owner/project isolation guard primitives.
- Scope-validated selective-deletion plans.
- Retention candidate selection with dry-run support.
- Schema migration for expiry, sensitivity and indexes.

Remaining:

- Expose selective forget/delete MCP tools.
- Execute retention cleanup only after explicit dry-run confirmation.
- Add broader adversarial end-to-end tests.

### PR #3 — Local SQLite starter mode — ✅ Complete

- Storage-adapter protocol and SQLite implementation.
- WAL mode, foreign keys and scoped destructive operations.
- Backend selection for SQLite, Supabase and PostgreSQL.
- Supabase-query-compatible local facade.
- Import/export compatibility and packaged SQLite schema.

### PR #4 — Safe automatic client installation — ✅ Complete

- Client configuration discovery on Linux, macOS and Windows.
- Backups, atomic writes and TOML/JSON validation.
- Safe merge that preserves unrelated configuration.
- Installation manifest, rollback and deterministic uninstall.

### PR #5 — Token-efficient context and project guardrails — ✅ Complete

- Intent-aware context builder and token budgets.
- Short, operational and detailed context layers.
- Relevance ranking, exact deduplication and deterministic compression.
- Token-use and token-savings metrics.
- Expired and untrusted-memory exclusion.
- Project, service and deployment guardrails.
- Safe credential references without storing secret values.

### PR #6 — Embeddings and hybrid-search foundation — 🟡 Partial

Completed:

- Configurable embedding-provider abstraction.
- Deterministic provider-free local embeddings.
- Lexical, semantic and weighted hybrid ranking core.
- Stored-vector reuse, call budgets, fallback metrics and deterministic ordering.
- Runtime integration with semantic-memory search.

Remaining:

- Add background indexing.
- Add search-quality and provider-cost regression benchmarks.

### PR #7 — Automatic session lifecycle foundation — 🟡 Partial

Completed:

- Reuse compatible active sessions.
- Prevent duplicate creation across reconnects.
- Heartbeat through `last_activity_at`.
- Close stale sessions using configurable idle time.
- End the previous interface session during cross-client handoff.
- Fix automatic session creation in `sync_session_state`.

Remaining:

- Resolve the active project automatically at session start.
- Load project guardrails before coding actions.
- Capture decisions, tasks, changed files and warnings automatically.
- Save checkpoints before context exhaustion or client shutdown.
- End sessions with completed work, pending work and the next safe action.
- Add configurable checkpoint cadence and token thresholds.
- Implement the complete local continuation contract.

### PR #8 — Git-grounded memory verification — ✅ Complete

- Repository root, branch, HEAD, remote and dirty-state detection.
- Commit, branch and repository-relative file verification.
- SHA-256 evidence for file contradictions.
- `verified`, `stale`, `contradicted`, `missing_source` and `unverified` states.
- Repository facts preferred over remembered repository state.
- Bounded verification history and last-verified provenance.
- Read-only, time-limited Git access and traversal protection.

### PR #9 — Code intelligence and impact graph foundation — 🟡 Partial

Completed:

- Python class, function and method indexing through AST.
- JavaScript/TypeScript class and function indexing.
- SQL table, view, function, trigger and index extraction.
- Stable symbol IDs, source coordinates, purpose and commit provenance.
- Typed `defines`, `contains`, `calls` and `inherits` relationships.
- Bounded symbol/file impact subgraphs.
- Detection of potentially existing symbols or responsibilities.
- Large-repository file-count, size and traversal limits.
- MCP tools `index_repository_symbols` and `analyze_symbol_impact`.

Remaining:

- Detect moved, renamed and deleted symbols across repository revisions.
- Persist symbol and relationship indexes in the configured storage backend.
- Link symbols to tests, decisions, tasks, services and deployments.
- Improve endpoint, migration and configuration-symbol extraction.
- Add language-aware call resolution beyond uniquely named local targets.

### PR #10 — Roadmap reconciliation — ✅ Complete

- Reconciled documentation with the merged foundation.
- Added implementation status suitable for release and contributor planning.

### PR #11 — Runtime security and isolation boundaries — ✅ Complete

- Applied sanitization to runtime write paths.
- Enforced owner/project isolation boundaries.
- Added cross-owner and cross-project validation tests.

### PR #12 — Persisted embedding lifecycle and reindexing — ✅ Complete

- Persisted embedding fingerprints, provider, dimensions and version metadata.
- Added bounded `reindex_memory_embeddings` tooling.
- Added retry, exponential backoff, call budgets and local fallback.

### PR #13 — Duplicate and contradiction intelligence — ✅ Complete

- Detects exact and semantic duplicate memories.
- Detects conflicting decisions, rules and numeric thresholds.
- Returns evidence, confidence and non-destructive recommendations.
- Supports explicit relationship metadata persistence.

### PR #14 — Deployment history and risk-aware execution — ✅ Complete

- Persists deployment history by project, owner, service, environment and commit.
- Records host, directory, restart command, tests, operator and rollback provenance.
- Compares repository, deployed and remembered commits without guessing ancestry.
- Classifies execution risk as low, medium or high.
- Requires confirmation for production, destructive and irreversible actions.
- Validates exact deployment targets before recording execution.
- Detects intent-versus-scope drift.
- Generates non-executing rollback plans.
- Provides SQLite and Supabase schema parity.

### PR #15 — Agent evaluation and provenance suite — ✅ Complete

- Deterministic expected-versus-observed evaluation cases.
- Weighted category and overall metrics with transparent evidence.
- Targeting, duplicate avoidance, stale detection, continuation, poisoned-memory resistance, handoff and provenance scenarios.
- Token savings measured only above a fixed quality floor.
- Checked-in regression scenarios and thresholds across Python 3.11–3.13.

### PR #16 — Local-first operational dashboard — 🟡 Partial

Completed:

- Dependency-free local HTTP dashboard.
- Localhost-only binding and rejection of remote interfaces.
- Bounded SQL reads with a maximum row limit.
- Read-only projects, sessions, decisions, tasks, warnings, file-memory, retention and deployment views.
- Project, table and bounded text filters.
- JSON and CSV export of the filtered snapshot.
- Escaped stored content and restrictive browser security headers.
- Browser-level HTTP, filtering, export and malicious-content tests.
- SQLite backend support.

Remaining:

- Add summarized sensitivity, verification, staleness and token-savings cards.
- Add selective deletion as a confirmed plan-only workflow.
- Add explicit pagination cursors for large datasets.
- Improve empty, loading and error states.

### PR #17 / PR #18 — Galaxy knowledge view — ✅ Complete

- Animated project knowledge graph.
- Nodes for projects, files, symbols, decisions, tasks, warnings and sessions.
- Typed relationships, clustering, zoom, filters, focus mode and search.
- Compact context selection from bounded subgraphs.
- Duplicate, contradiction, stale-memory and orphan visualization.
- Performance limits for large graphs.

### PR #20 — Nested secret redaction — ✅ Complete

- Redacts sensitive values inside nested dictionaries, lists and tuples.
- Preserves payload shape and records security findings.

### PR #21 — Roadmap secret-redaction reconciliation — ✅ Complete

- Marks automatic secret redaction complete in the public roadmap.

## Product scope decision

### Teams, memberships, roles and remote collaborative dashboard — 🚫 Out of scope

PR #23 was closed without merge and issue #22 was closed as not planned.

Persistent Memory MCP is intended to remain:

- a personal local installation;
- backed by private local SQLite by default;
- accessed through local MCP clients;
- visualized through a localhost-only dashboard;
- isolated by project and local owner identity.

The following are not product milestones:

- workspace membership and invitations;
- owner/admin/member/reader roles;
- multi-user shared memory;
- public or remotely hosted collaborative dashboard;
- billing or organization administration.

## Current product position

The secure local-first backend, context engine, session foundation, hybrid search, Git verification, code intelligence, duplicate detection, deployment-risk core, evaluation suite, local dashboard and Galaxy View are available. The remaining product work is focused on safe local data control, operational completeness, recovery and distribution.

## Next delivery milestones

### Next PR — Selective deletion and confirmed retention execution — ⬜ Planned

- Expose bounded MCP tools for selective forget/delete planning.
- Keep dry-run as the default and require explicit confirmation before mutation.
- Display exact record counts, scopes and identifiers before deletion.
- Reject owner/project scope expansion and stale confirmation tokens.
- Record audit metadata for planned and executed operations.
- Add adversarial and integration tests for accidental deletion prevention.
- Document the workflow in public docs and Notion.

### Verified local backup and restore — ⬜ Planned

- Create consistent SQLite backups while WAL mode is active.
- Validate source and backup integrity.
- Refuse accidental overwrite during restore.
- Support preview, explicit confirmation and rollback-safe restore.
- Document migration and disaster recovery procedures.

### Dashboard completion — ⬜ Planned

- Add pagination cursors.
- Add memory, verification, staleness, sensitivity, token and storage cards.
- Add safe local maintenance actions backed by confirmation workflows.
- Improve accessibility, empty states and error handling.

### Automatic continuation completion — ⬜ Planned

- Resolve active projects automatically.
- Capture important session changes and checkpoints.
- Persist the next safe action before shutdown or context exhaustion.
- Validate continuation quality across supported local clients.

### Distribution and publication — ⬜ Planned

- Package publication and release automation.
- MCP Registry submission.
- Versioned upgrade and migration documentation.
- Clean installation, update and uninstall validation.
- Optional Docker packaging only when it preserves localhost-only operation.

## Final product validation

- [ ] Clean local installation and upgrade.
- [x] Multi-client configuration, backup and rollback for client configuration.
- [x] SQLite local-first storage.
- [x] Owner/project isolation foundation.
- [x] Runtime sanitization and poisoned-memory resistance foundation.
- [ ] Selective deletion and confirmed retention execution.
- [ ] Verified local backup and restore.
- [ ] Complete automatic cross-client memory recovery.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol-level duplicate avoidance and full impact analysis.
- [x] Project, service and deployment-target guardrail foundation.
- [x] Measurable token savings under regression thresholds.
- [ ] Complete operational dashboard.
- [x] Galaxy knowledge view.
- [ ] Release and registry publication.
- [x] Teams, roles and remote collaboration excluded from scope.
