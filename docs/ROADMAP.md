# Persistent Memory MCP delivery roadmap

Persistent Memory MCP is a **local-first personal memory system for MCP-compatible development agents**. The v0.3 foundation established recoverable SQLite storage, explicit upgrades and cross-platform packaging. The active roadmap now focuses on turning stored memory into a **measurable Context Compiler** that can deliver only the context required for the next safe action.

This document mirrors the canonical post-v0.3 roadmap maintained in Notion. Product scope remains one local installation, localhost-only operational UI, project/owner isolation, no shared workspace roles and no automatic code execution.

## Status legend

- ✅ **Complete** — merged, integrated and covered by repository tests.
- 🟡 **In review / partial** — implementation exists but the end-to-end gate is not fully closed.
- ⬜ **Planned** — sequenced work not started yet.
- 🚫 **Out of scope** — intentionally excluded from the product direction.

## Delivered foundation

### Local data safety and recovery — ✅ Complete foundation

- private SQLite storage with WAL and foreign keys;
- owner/project isolation and secret redaction;
- WAL-safe backups using SQLite's backup API;
- SHA-256 backup manifests and integrity verification;
- read-only `memory-mcp health` diagnostics;
- two-phase confirmed restore with a verified safety backup and rollback;
- versioned checksum-verified SQLite migrations;
- explicit `memory-mcp-migrate` preview/apply flow;
- fail-closed startup when an existing database needs migration;
- deterministic close semantics for context-managed SQLite connections.

### Package and upgrade safety — ✅ Complete foundation

- SQLite-first core dependencies with optional Supabase/PostgreSQL extras;
- validated immutable RuntimeSettings foundation;
- Ubuntu, Windows and macOS CI across Python 3.11–3.13;
- wheel/sdist build and clean-install validation;
- real installed v0.2.0 → v0.3.0 migration regression with existing data preserved;
- release-artifact checksums and backup-first rollback documentation.

### Memory, search and development intelligence — ✅/🟡 Foundation

Complete foundations:

- decisions, tasks, warnings, sessions, checkpoints and file memory;
- hybrid semantic + lexical search;
- persisted embedding lifecycle and local fallback;
- Git repository/branch/commit verification;
- code symbol extraction and bounded impact graphs;
- duplicate/contradiction intelligence;
- deployment history, risk gates and evaluation regressions;
- localhost dashboard and bounded Galaxy knowledge view.

Known partial areas that the new roadmap addresses:

- context token accounting was historically based on a fixed character estimator;
- repository retrieval is not yet progressive from map → file → symbol → fragment;
- symbol history across revisions is not yet persistent;
- automatic continuation checkpoints remain partial;
- Galaxy still needs an operational projection rather than being only a knowledge visualization.

## Post-v0.3 mandatory sequence

The following order is intentional. A later step should not bypass an earlier contract because every layer depends on the evidence and budget semantics established before it.

### 1. Versioned Context Packet and real token accounting — 🟡 In review

**Notion:** MEM-36  
**GitHub:** Issue #56 / PR #60

Goals:

- expose a stable `Context Packet` contract through the real context-delivery path;
- include packet version, objective, next safe action when known, provenance sources and verification status;
- enforce a hard serialized token budget;
- identify the active model/tokenizer and whether counting is exact or a deterministic fallback;
- report selected, dropped, compressed and token-cost metrics per context block;
- preserve the existing `build_context()` contract for legacy callers;
- keep a provider-free local fallback when an exact tokenizer is unavailable;
- retain compatibility with existing 256-token context requests through a compact control profile.

Current PR #60 validation:

- optional exact reference: `tiktoken:o200k_base` for `gpt-4o`;
- deterministic fallback: `deterministic-heuristic-v2`;
- Spanish fixture: 69 reference tokens vs 80 fallback tokens — **15.94% error**;
- source-code fixture: 138 reference tokens vs 140 fallback tokens — **1.45% error**;
- configured guardrail: worst fixture error ≤ 40%; current worst case **15.94%**;
- dedicated packet/tokenization regressions run on Ubuntu, Windows and macOS.

Exit criteria:

- [ ] exact PR head passes the complete Quality matrix;
- [ ] README, ROADMAP, IMPLEMENTATION_STATUS and Notion describe the same validated contract;
- [ ] PR #60 merged and MEM-36 marked complete.

### 2. Progressive repository retrieval — ⬜ Planned

After Step 1 is merged, retrieval evolves from broad context loading to bounded progressive expansion:

1. repository/project map;
2. relevant files;
3. relevant symbols;
4. exact snippets/fragments only when necessary.

Required properties:

- path normalization and traversal protection;
- deterministic ordering and bounded reads;
- ignore-policy enforcement;
- provenance on every returned fragment;
- explicit limits for files, symbols, bytes and snippets;
- token cost measured through the Context Packet contract rather than a separate estimator.

### 3. Code provenance and symbol evolution — ⬜ Planned

- persist symbol identity across commits/revisions;
- classify added, modified, moved, renamed and deleted symbols;
- bind symbol evidence to repository path + commit/ref;
- link symbols to tests, tasks, decisions and deployments where evidence exists;
- avoid stale-code claims when the repository has changed.

### 4. Context quality and regression guardrails — ⬜ Planned

- define golden continuation scenarios;
- measure relevance, provenance coverage and unnecessary-context rate;
- compare token cost against task completion quality;
- test poisoned/untrusted memory and stale code evidence;
- make quality regressions visible in CI before context behavior ships.

### 5. Operational project map / Galaxy — ⬜ Planned

Galaxy becomes an operational projection only after Context Packet, retrieval and code provenance are measurable.

Planned views:

- active work and next safe actions;
- stale/contradicted/unverified memories;
- repository hotspots and symbol relationships;
- token-cost and retrieval diagnostics;
- backup/health state and maintenance readiness;
- bounded drill-down without exposing the dashboard remotely.

## Parallel non-blocking work

These items may receive maintenance fixes but must not displace the mandatory sequence above:

- dashboard pagination and accessible empty/loading/error states;
- automatic project resolution and continuation capture;
- provider-specific configuration cleanup;
- broader embedding/search benchmarks;
- optional Supabase/PostgreSQL adapter maintenance.

## Product scope decision — 🚫 No collaborative SaaS

Persistent Memory MCP remains:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- isolated by project and local owner identity;
- compatible with local MCP clients.

Workspace invitations, shared memberships, team-role hierarchies, billing and a public remote collaborative dashboard are not milestones.

## Definition of done for each roadmap step

A step is not complete until all of the following are true:

1. the code path is integrated into the real product rather than only exposed as a helper;
2. deterministic tests cover success, failure and boundary behavior;
3. the relevant Ubuntu/Windows/macOS CI gate passes;
4. measurable evidence is recorded when the step introduces a quality or cost claim;
5. README, this ROADMAP, IMPLEMENTATION_STATUS and the corresponding Notion task agree;
6. the implementation does not broaden local-first scope or silently execute destructive/code actions.

## Current recommended order

1. Finish and merge **PR #60 — Context Packet + token accounting**.
2. Start **progressive repository retrieval** only after the packet contract is stable.
3. Add **persistent code provenance/symbol evolution** on top of bounded retrieval.
4. Add **context quality regression guardrails** with measurable golden scenarios.
5. Evolve **Galaxy into an operational project map** using the verified data from the previous layers.
