# Persistent Memory MCP delivery roadmap

This roadmap reflects the repository state through PR #15. It separates completed foundations from partial integrations and planned product work.

## Status legend

- ✅ **Complete** — implemented, integrated and covered by repository tests.
- 🟡 **Partial** — useful foundation exists, but one or more end-to-end paths remain.
- ⬜ **Planned** — not implemented yet.

## Delivered foundation

### PR #1 — Product CLI and multi-client onboarding — ✅ Complete

Python distribution, CLI commands, client configuration and Python 3.11–3.13 CI foundation.

### PR #2 — Security, isolation and retention foundation — 🟡 Partial

Sanitization, stored-instruction detection, owner/project isolation, sensitivity, TTL, deletion plans and retention dry runs are implemented. Selective deletion tools and confirmed cleanup execution remain.

### PR #3 — Local SQLite starter mode — ✅ Complete

SQLite storage adapter, WAL, foreign keys, scoped operations and local/remote backend selection.

### PR #4 — Safe automatic client installation — ✅ Complete

Configuration discovery, backups, atomic writes, safe merge, rollback and uninstall.

### PR #5 — Token-efficient context and project guardrails — ✅ Complete

Intent-aware context, token budgets, deterministic compression, project/service guardrails and token-savings metrics.

### PR #6 — Embeddings and hybrid-search foundation — 🟡 Partial

Local embeddings, hybrid ranking, vector reuse, budgets and fallback metrics are implemented. Background indexing and provider-cost benchmarks remain.

### PR #7 — Automatic session lifecycle foundation — 🟡 Partial

Session reuse, heartbeats, stale closure and cross-client handoff are implemented. Full automatic project resolution, checkpoints and continuation capture remain.

### PR #8 — Git-grounded memory verification — ✅ Complete

Repository, branch, commit and file verification with stale, contradicted, missing and unverified states.

### PR #9 — Code intelligence and impact graph foundation — 🟡 Partial

Python, JavaScript, TypeScript and SQL symbol indexing plus bounded impact graphs are implemented. Persistent indexes and cross-revision symbol tracking remain.

### PR #10 — Roadmap reconciliation — ✅ Complete

Repository documentation reconciled with the delivered foundation.

### PR #11 — Runtime security and isolation boundaries — ✅ Complete

Runtime sanitization and cross-owner/cross-project isolation enforcement.

### PR #12 — Persisted embedding lifecycle and reindexing — ✅ Complete

Embedding fingerprints, bounded reindexing, retries, backoff and local fallback.

### PR #13 — Duplicate and contradiction intelligence — ✅ Complete

Exact and semantic duplicate detection, contradiction evidence and non-destructive recommendations.

### PR #14 — Deployment history and risk-aware execution — ✅ Complete

Deployment provenance, commit drift, exact-target validation, risk classification, confirmation gates, rollback plans and SQLite/Supabase parity.

### PR #15 — Agent evaluation and provenance suite — ✅ Complete

- Deterministic expected-versus-observed evaluation cases.
- Weighted category and overall metrics with transparent evidence.
- Targeting, duplicate avoidance, stale detection, continuation, poisoned-memory resistance, handoff and provenance scenarios.
- Token-savings measurement under fixed quality floors.
- Explainable source, verification state, confidence and evidence records.
- Bounded `run_agent_evaluation` MCP tool without arbitrary code execution.
- Checked-in multi-agent handoff and poisoned-memory fixtures.
- Regression thresholds enforced by the Quality workflow on Python 3.11–3.13.

## Current product position

The secure local-first backend, context engine, session foundation, hybrid search, Git verification, code intelligence, duplicate detection, deployment-risk controls and reproducible evaluation suite are available. The project is suitable for technical evaluation and continued development, but it is not yet the complete dashboard-and-team product.

## Next delivery milestones

### PR #16 — Local-first operational dashboard — ⬜ Planned

Localhost-only dashboard for projects, sessions, decisions, tasks, warnings, file memory, search, export, retention, verification and deployment history across SQLite and Supabase.

### PR #17 — Galaxy knowledge view — ⬜ Planned

Animated typed knowledge graph with clustering, filters, search, compact-context selection and performance limits.

### PR #18 — Teams, roles and remote dashboard — ⬜ Planned

Supabase Auth, workspace membership, invitations, roles, shared-project RLS, audit trail and secure remote access.

### PR #19 — Distribution, deployment and publication — ⬜ Planned

Docker, deployment guides, release automation, package publication, MCP Registry submission, upgrades, backup and disaster recovery.

## Final product validation

- [ ] Clean local installation and upgrade.
- [x] Multi-client configuration, backup and rollback.
- [ ] Full SQLite and Supabase behavioral parity.
- [x] End-to-end cross-owner and cross-project isolation foundation.
- [x] Sanitization and poisoned-memory resistance foundation.
- [ ] Selective deletion and confirmed retention execution.
- [ ] Complete automatic cross-client memory recovery.
- [x] Git-grounded stale-memory classification foundation.
- [ ] Persistent symbol-level duplicate avoidance and full impact analysis.
- [x] Project, service and deployment-target guardrail foundation.
- [x] Measurable token savings under regression thresholds.
- [x] Reproducible agent evaluation and provenance thresholds.
- [ ] Operational dashboard and Galaxy View.
- [ ] Teams, roles and remote access.
- [ ] Release, registry publication and disaster-recovery documentation.
