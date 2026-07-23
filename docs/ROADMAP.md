# Persistent Memory MCP delivery roadmap

This roadmap reflects the repository state through PR #13. It separates delivered capabilities from partial integrations and future product work so merged foundations are not mistaken for complete end-to-end features.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.

## Delivered foundation

### PR #1 — Product CLI and multi-client onboarding — ✅ Complete

- Package and command aliases for `persistent-memory-mcp`.
- `init`, `doctor`, `status` and `serve` commands.
- Configuration generation for Codex, Claude Code, OpenCode and Antigravity.
- Python 3.11–3.13 CI foundation.

### PR #2 — Security, isolation and retention foundation — 🟡 Partial

Delivered primitives:

- Secret redaction and stored-instruction detection.
- Untrusted-content metadata, size limits, provenance and TTL metadata.
- Owner/project isolation guards.
- Selective-deletion plans and retention dry runs.

Remaining:

- Expose selective forget/delete MCP tools.
- Execute retention cleanup only after explicit confirmation.
- Add adversarial cross-owner and cross-project end-to-end tests.

### PR #3 — Local SQLite starter mode — ✅ Complete

- SQLite storage adapter with WAL, foreign keys and scoped destructive operations.
- Backend selection for SQLite, Supabase and PostgreSQL.
- Import/export compatibility and packaged schema.

### PR #4 — Safe automatic client installation — ✅ Complete

- Client configuration discovery on Linux, macOS and Windows.
- Backups, atomic writes and safe config merging.
- Installation manifest, rollback and deterministic uninstall.

### PR #5 — Token-efficient context and project guardrails — ✅ Complete

- Intent-aware context building and token budgets.
- Deterministic relevance ranking, deduplication and compression.
- Token savings metrics and exclusion of expired or untrusted memory.
- Project, service and deployment-target guardrails.

### PR #6 — Embeddings and hybrid search foundation — 🟡 Partial

- Configurable embedding provider abstraction.
- Deterministic local embeddings.
- Lexical, semantic and weighted hybrid ranking.
- Stored-vector reuse, call budgets and fallback metrics.
- Runtime semantic-memory search integration.

Remaining:

- Background indexing.
- Search-quality and provider-cost regression benchmarks.

### PR #7 — Automatic session lifecycle foundation — 🟡 Partial

- Reuse compatible active sessions and avoid reconnect duplicates.
- Heartbeats, stale-session closure and cross-client handoff.

Remaining:

- Resolve active projects automatically at session start.
- Capture decisions, tasks, changed files and warnings automatically.
- Save checkpoints before context exhaustion or shutdown.
- Complete the shared continuation contract.

### PR #8 — Git-grounded memory verification — ✅ Complete

- Repository, branch, HEAD, remote and dirty-state detection.
- Commit, branch and file verification.
- Evidence-backed stale, contradicted and missing-source states.
- Traversal protection and bounded verification history.

### PR #9 — Code intelligence and impact graph foundation — 🟡 Partial

- Python, JavaScript, TypeScript and SQL symbol extraction.
- Stable symbol IDs and typed relationships.
- Bounded symbol/file impact graphs.
- MCP tools for indexing and impact analysis.

Remaining:

- Persist symbol indexes in configured storage.
- Detect moved, renamed and deleted symbols across revisions.
- Link symbols to tests, decisions, tasks, services and deployments.

### PR #10 — Roadmap reconciliation and implementation status — ✅ Complete

- Documentation reconciled with PRs #1–#9.
- Delivered, partial and planned capabilities separated.

### PR #11 — Runtime security and isolation boundaries — ✅ Complete

- Sanitization applied centrally to table write paths.
- Owner and project validation enforced around reads and writes.
- Security metadata preserved with sanitized records.
- Runtime installation is additive and idempotent.

### PR #12 — Persisted embedding lifecycle and reindexing — ✅ Complete

- Stable content fingerprints and embedding metadata.
- Stale-vector detection by content and provider.
- Explicit bounded `reindex_memory_embeddings` MCP tool.
- Retry, exponential backoff, call budgets and local fallback.
- Current embeddings skipped unless force is requested.

### PR #13 — Duplicate and contradiction intelligence — 🟡 In review

- Exact and semantic duplicate detection.
- Related-memory and contradiction classification.
- Numeric-threshold and opposing-negation evidence.
- Recommendations: `merge`, `keep_both`, `mark_related` and `ignore`.
- Bounded MCP tool `analyze_memory_relationships`.
- Explicit non-destructive relationship metadata persistence.
- Confidence and evidence for human resolution.

Future extensions:

- Duplicate tasks, code responsibilities, configuration and service registrations.
- Superseded-decision workflows with preserved history.
- Human review and resolution states across dashboards.

## Current product position

The project now provides a secure local-first backend, token-efficient context engine, session foundation, hybrid search with persisted embedding lifecycle, Git verification, code intelligence and evidence-based duplicate/contradiction analysis. It is suitable for technical evaluation and continued development, but it is not yet the full dashboard-and-team product.

## Next delivery milestones

### PR #14 — Deployment history and risk-aware execution — ⬜ Planned

- Persist deployments by project, service, environment and commit SHA.
- Record tests, result, timestamp, operator and rollback target.
- Compare repository, deployed and remembered commits.
- Classify actions as low, medium or high risk.
- Require stronger confirmation for production or destructive actions.
- Detect intent-versus-scope drift.
- Provide rollback plans and deployment provenance.

### PR #15 — Agent evaluation and provenance suite — ⬜ Planned

- Evaluate project and service identification accuracy.
- Measure duplicate avoidance, stale-memory detection and continuation quality.
- Measure token savings under fixed quality thresholds.
- Evaluate prompt-injection and poisoned-memory resistance.
- Add reproducible multi-agent handoff scenarios.

### PR #16 — Local-first operational dashboard — ⬜ Planned

- Localhost-only dashboard command by default.
- Projects, sessions, decisions, tasks, warnings and file memory.
- Search, export, selective deletion and retention controls.
- Sensitivity, storage, token-savings and verification visibility.
- SQLite and Supabase support.

### PR #17 — Galaxy knowledge view — ⬜ Planned

- Animated project knowledge graph.
- Typed nodes and relationships with clustering, filters and search.
- Compact-context selection from subgraphs.
- Duplicate, contradiction, stale-memory and orphan visualization.

### PR #18 — Teams, roles and remote dashboard — ⬜ Planned

- Supabase Auth, workspace membership and invitations.
- Owner, admin, member and reader roles.
- Shared-project RLS and audit trails.
- Private and shared memories.

### PR #19 — Distribution, deployment and publication — ⬜ Planned

- Docker image and deployment guides.
- Release automation and package publication.
- MCP Registry submission.
- Upgrade, migration, backup, restore and disaster-recovery documentation.
- Optional privacy-preserving telemetry, disabled by default.

## Final product validation

- [ ] Clean local installation and upgrade.
- [x] Multi-client configuration, backup and rollback.
- [ ] Full SQLite and Supabase behavioral parity.
- [ ] End-to-end cross-owner and cross-project isolation.
- [x] Central sanitization on runtime table write paths.
- [ ] Selective deletion and confirmed retention execution.
- [ ] Complete automatic cross-client memory recovery.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol-level duplicate avoidance and full impact analysis.
- [x] Persisted embedding lifecycle and bounded reindexing.
- [x] Evidence-based memory duplicate and contradiction analysis.
- [x] Project, service and deployment-target guardrail foundation.
- [x] Measurable token savings under regression thresholds.
- [ ] Deployment history and risk-aware execution.
- [ ] Operational dashboard and Galaxy View.
- [ ] Teams, roles and remote access.
- [ ] Release, registry publication and disaster-recovery documentation.
