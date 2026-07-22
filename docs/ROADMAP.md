# Persistent Memory MCP delivery roadmap

This roadmap keeps the post-v0.2 work separated into focused, reviewable pull requests while preserving the complete product vision: secure, local-first, token-efficient, visual and deployable.

## PR #2 — Security, isolation and retention

- [x] Secret redaction primitives
- [x] Stored-instruction detection and untrusted-content metadata
- [x] Content-size limits
- [x] Provenance normalization
- [x] TTL/expiry metadata
- [x] Owner/project isolation guard primitives
- [x] Scope-validated selective deletion plans
- [x] Retention candidate selection with dry-run support
- [x] Schema migration for expiry, sensitivity and indexes
- [ ] Apply sanitization to every memory write path
- [ ] Enforce project/owner boundary validation in all service paths
- [ ] Expose selective forget/delete MCP tools
- [ ] Execute retention cleanup after dry-run confirmation
- [ ] Add adversarial and end-to-end cross-owner isolation tests

## PR #3 — Local SQLite starter mode

- [x] Storage-adapter interface
- [x] SQLite schema and initialization
- [x] Local health check and scoped destructive operations
- [x] Backend selection in `memory-mcp init`
- [x] `MEMORY_BACKEND` and `SQLITE_PATH` client configuration
- [x] Connect the existing MCP service layer through a SQLite-compatible client facade
- [x] Import/export compatibility through the existing memory bundle tools
- [x] Backend query-shape and CLI parity tests
- [x] Package the SQLite schema in built distributions

## PR #4 — Safe automatic client installation

- [x] Detect Codex, Claude Code, OpenCode and Antigravity configuration paths
- [x] Platform-specific path handling and explicit path overrides
- [x] Back up existing files before changes
- [x] Merge without removing unrelated MCP servers or preferences
- [x] Validate TOML and JSON before replacement
- [x] Atomic configuration writes
- [x] Installation manifest
- [x] `install`, `uninstall`, `backups` and `rollback` commands
- [x] Optional installation from `memory-mcp init`
- [x] Interactive confirmation and `--yes` automation mode
- [x] Deterministic uninstall of only the managed MCP entry
- [x] End-to-end safety tests for merge, backup, manifest, uninstall and rollback

## PR #5 — Token-efficient context engine

- [x] Intent-aware context builder
- [x] Configurable token budgets
- [x] Short, operational and detailed memory layers
- [x] Relevance ranking and exact deduplication
- [x] Automatic session/checkpoint compression
- [x] Token-use and token-savings measurements
- [x] Provenance included in returned context
- [x] Safe exclusion of expired and untrusted memory
- [x] Context controls exposed through optimizer request metadata and MCP runtime environment
- [x] Benchmark fixtures and savings regression thresholds
- [x] Compatibility tests for the existing optimizer interface

## PR #6 — Embeddings and hybrid search

- [ ] Configurable embedding provider
- [ ] Background indexing and reindex command
- [ ] Semantic plus lexical ranking
- [ ] Provider-free fallback
- [ ] Cost, retry and rate-limit controls
- [ ] Contradiction and near-duplicate detection

## PR #7 — Local-first operational dashboard

- [ ] Local dashboard command and localhost-only default
- [ ] Projects and sessions
- [ ] Decisions, tasks, warnings and file memory
- [ ] Search, export and selective deletion
- [ ] Retention, sensitivity and storage visibility
- [ ] Token-budget and estimated-savings analytics
- [ ] SQLite and Supabase backend support

## PR #8 — Galaxy knowledge view

- [ ] Animated project knowledge graph
- [ ] Nodes for projects, files, decisions, tasks, warnings and sessions
- [ ] Typed relationships and domain clustering
- [ ] Zoom, filters, focus mode and search
- [ ] Select a subgraph to build compact agent context
- [ ] Duplicate, contradiction and orphan-node visualization
- [ ] Performance limits for large graphs

## PR #9 — Teams, roles and remote dashboard

- [ ] Supabase Auth integration
- [ ] Workspace membership and invitations
- [ ] Owner, admin, member and reader roles
- [ ] Shared-project RLS policies
- [ ] Private and shared memories
- [ ] Audit trail and permission tests
- [ ] Secure remote dashboard deployment

## PR #10 — Distribution, deployment and publication

- [ ] Docker image
- [ ] Render/Railway deployment guides
- [ ] Release automation and package publication
- [ ] MCP Registry submission
- [ ] Versioned upgrade and migration documentation
- [ ] Backup, restore and disaster-recovery documentation
- [ ] Optional privacy-preserving telemetry, disabled by default

## Final product validation

- [ ] Clean local installation and upgrade
- [ ] Multi-client configuration and rollback
- [ ] SQLite and Supabase parity
- [ ] Cross-owner and cross-project isolation
- [ ] Secret redaction and prompt-injection resistance
- [ ] Selective deletion and retention execution
- [ ] Cross-client memory recovery
- [ ] Measurable token savings under fixed budgets
- [ ] Operational dashboard and Galaxy View
- [ ] Export, backup, restore and full-project deletion
