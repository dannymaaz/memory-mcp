# Persistent Memory MCP delivery roadmap

This roadmap reflects merged work through PR #26. Persistent Memory MCP is a local-first personal application: one local installation, one private localhost dashboard and no shared workspace or multi-user role model.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Product CLI and local onboarding — ✅ Complete

- `memory-mcp` and `persistent-memory-mcp` command aliases.
- `init`, `doctor`, `status` and `serve` commands.
- Safe client configuration with backup, rollback and uninstall support.
- Python 3.11–3.13 CI coverage.

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

### Context, search and embeddings — ✅ Complete foundation

- Intent-aware context and token budgets.
- Semantic and lexical hybrid search.
- Persisted embedding fingerprints, bounded reindexing, retries and local fallback.
- Token-savings and regression metrics.

Remaining refinements:

- Background indexing.
- Broader search-quality and provider-cost benchmarks.

### Session continuity — 🟡 Partial

Completed:

- Session reuse, heartbeat and stale-session closure.
- Cross-client handoff and checkpoints.

Remaining:

- Fully automatic project resolution at session start.
- Automatic milestone capture before shutdown or context exhaustion.
- Complete local continuation contract and quality validation.

### Git verification and code intelligence — 🟡 Partial

Completed:

- Repository, branch, commit, file and working-tree verification.
- Stale, contradicted, missing-source and unverified states.
- Python, JavaScript, TypeScript and SQL symbol extraction.
- Bounded impact graphs.

Remaining:

- Persistent symbol history across revisions.
- Moved, renamed and deleted symbol tracking.
- Links from symbols to tests, tasks and deployments.

### Duplicate, contradiction and deployment safety — ✅ Complete foundation

- Duplicate and contradiction recommendations with evidence and confidence.
- Deployment history and exact-target validation.
- Risk classification, confirmation gates and rollback plans.
- Evaluation and provenance regression suite.

### Local dashboard and Galaxy View — 🟡 Partial

Completed:

- Localhost-only dashboard.
- Read-only project, session, decision, task, warning, retention and deployment views.
- Bounded filtering and JSON/CSV export.
- Galaxy knowledge visualization with bounded graphs.
- Confirmed deletion MCP workflow available as the safe maintenance foundation.

Remaining:

- Explicit pagination cursors.
- Operational summary cards for storage, staleness, verification and sensitivity.
- Polished empty, loading and error states.
- Dashboard controls that consume the confirmed deletion workflow safely.

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

## Next delivery milestones

### 1. Verified local backup and restore — ⬜ Planned

- Create consistent SQLite backups while WAL mode is active.
- Add SHA-256 manifests, schema/version metadata and integrity validation.
- Support full and bounded restore previews.
- Refuse accidental overwrite and require explicit confirmation.
- Document migration and disaster-recovery procedures.

### 2. Integrity and recovery — ⬜ Planned

- Detect corrupted databases, missing references and orphan records.
- Validate indexes and repair recoverable inconsistencies.
- Handle interrupted restore and insufficient disk space safely.

### 3. Dashboard completion — ⬜ Planned

- Add pagination, summary cards and accessible maintenance workflows.
- Surface backup health, last verified backup and database size.
- Integrate confirmed deletion and restore previews without bypassing safety gates.

### 4. Automatic continuation completion — ⬜ Planned

- Resolve active projects automatically.
- Capture important session changes and checkpoints.
- Persist the next safe action before shutdown or context exhaustion.

### 5. Distribution and publication — ⬜ Planned

- Package publication and release automation.
- Versioned upgrade and migration documentation.
- Clean install, update and uninstall validation.
- MCP Registry submission.

## Final product validation

- [ ] Clean local installation and upgrade.
- [x] Safe multi-client configuration and rollback.
- [x] SQLite local-first storage.
- [x] Owner/project isolation.
- [x] Runtime sanitization and poisoned-memory resistance.
- [x] Selective deletion and confirmed retention execution.
- [ ] Verified local backup and restore.
- [ ] Complete automatic continuation.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol history and full impact analysis.
- [x] Deployment-target guardrails and regression evaluation.
- [ ] Complete operational dashboard.
- [x] Galaxy knowledge view.
- [ ] Release and registry publication.
- [x] Teams, roles and remote collaboration excluded from scope.
