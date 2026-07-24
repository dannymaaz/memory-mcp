# Persistent Memory MCP delivery roadmap

This roadmap reflects the repository state through PR #14. It separates completed capabilities from partial integrations and future product work so that a merged foundation is not mistaken for a finished end-to-end feature.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.

## Delivered foundation

### PR #1 — Product CLI and multi-client onboarding — ✅ Complete

- Python distribution renamed to `persistent-memory-mcp`.
- `memory-mcp` and `persistent-memory-mcp` command aliases.
- `init`, `doctor`, `status` and `serve` commands.
- Configuration generation for Codex, Claude Code, OpenCode and Antigravity.
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
- Implement the complete shared continuation contract.

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

## Current product position

The secure local-first backend, context engine, session foundation, hybrid search, Git verification, code intelligence, duplicate detection and deployment-risk core are available. The project is suitable for technical evaluation and continued development, but it is not yet the complete dashboard-and-team product.

## Next delivery milestones

### PR #15 — Agent evaluation and provenance suite — ⬜ Planned

- Evaluate project and service identification accuracy.
- Measure duplicate avoidance and wrong-target prevention.
- Measure stale-memory detection and continuation accuracy.
- Measure token savings under fixed quality thresholds.
- Evaluate prompt-injection and poisoned-memory resistance.
- Add reproducible multi-agent handoff scenarios.
- Explain source, verification state and confidence for important facts.

### PR #16 — Local-first operational dashboard — ⬜ Planned

- Local dashboard command with localhost-only default.
- Projects, sessions, decisions, tasks, warnings and file memory.
- Search, export, selective deletion and retention controls.
- Sensitivity, storage and token-savings visibility.
- Verification, staleness, deployment and risk history.
- SQLite and Supabase backend support.

### PR #17 — Galaxy knowledge view — ⬜ Planned

- Animated project knowledge graph.
- Nodes for projects, files, symbols, decisions, tasks, warnings and sessions.
- Typed relationships, clustering, zoom, filters, focus mode and search.
- Select subgraphs to build compact agent context.
- Visualize duplicates, contradictions, stale memories and orphan nodes.
- Enforce performance limits for large graphs.

### PR #18 — Teams, roles and remote dashboard — ⬜ Planned

- Supabase Auth integration.
- Workspace membership and invitations.
- Owner, admin, member and reader roles.
- Shared-project RLS policies.
- Private and shared memories.
- Audit trail and permission tests.
- Secure remote dashboard deployment.

### PR #19 — Distribution, deployment and publication — ⬜ Planned

- Docker image.
- Render and Railway deployment guides.
- Release automation and package publication.
- MCP Registry submission.
- Versioned upgrade and migration documentation.
- Backup, restore and disaster-recovery documentation.
- Optional privacy-preserving telemetry, disabled by default.

## Final product validation

- [ ] Clean local installation and upgrade.
- [x] Multi-client configuration, backup and rollback.
- [ ] Full SQLite and Supabase behavioral parity.
- [x] End-to-end cross-owner and cross-project isolation foundation.
- [x] Sanitization on runtime write paths and poisoned-memory resistance foundation.
- [ ] Selective deletion and confirmed retention execution.
- [ ] Complete automatic cross-client memory recovery.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol-level duplicate avoidance and full impact analysis.
- [x] Project, service and deployment-target guardrail foundation.
- [x] Measurable token savings under regression thresholds.
- [ ] Operational dashboard and Galaxy View.
- [ ] Teams, roles and remote access.
- [ ] Release, registry publication and disaster-recovery documentation.
