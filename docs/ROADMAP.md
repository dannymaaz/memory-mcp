# Persistent Memory MCP delivery roadmap

This roadmap keeps the post-v0.2 work separated into focused, reviewable pull requests while preserving the complete product vision: secure, local-first, token-efficient, verifiable and safe for long-running coding-agent workflows.

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
- [x] Project, service and deployment guardrails
- [x] Safe credential references without secret values

## PR #6 — Embeddings and hybrid search

- [x] Configurable embedding-provider foundation
- [x] Deterministic provider-free local fallback
- [x] Semantic plus lexical ranking foundation
- [x] Embedding-call budgets and stored-vector reuse
- [ ] Integrate hybrid ranking into `search_semantic_memory`
- [ ] Persisted embedding lifecycle and schema support
- [ ] Background indexing and reindex command
- [ ] Remote-provider retry, backoff and rate-limit controls
- [ ] Contradiction and near-duplicate detection foundation
- [ ] Search quality and cost regression benchmarks

## PR #7 — Automatic agent session lifecycle

- [ ] Automatically resolve the active project at session start
- [ ] Load project guardrails before coding actions
- [ ] Create and resume sessions without requiring manual prompts
- [ ] Capture decisions, tasks, changed files and warnings at meaningful milestones
- [ ] Save checkpoints before context exhaustion or client shutdown
- [ ] End sessions with completed work, remaining work and the next safe action
- [ ] Add configurable checkpoint cadence and token thresholds
- [ ] Prevent duplicate session creation across reconnects
- [ ] Provide a shared cross-client continuation contract

The continuation contract must expose stable fields such as:

- `current_goal`
- `completed_work`
- `pending_work`
- `critical_rules`
- `verified_files`
- `open_questions`
- `next_safe_action`
- `do_not_touch`
- `repository_state`

## PR #8 — Git-grounded memory verification and staleness

- [ ] Bind checkpoints to repository, branch, commit SHA and pull request
- [ ] Verify that referenced commits, branches and files still exist
- [ ] Compare remembered file state with the active repository
- [ ] Mark memories as `verified`, `stale`, `contradicted`, `missing_source` or `unverified`
- [ ] Prefer repository state over remembered state when they disagree
- [ ] Detect merged, deleted or rebased branches
- [ ] Detect when production and repository commits differ
- [ ] Refresh or supersede stale memories without silently deleting history
- [ ] Add provenance timestamps and last-verified commit metadata

## PR #9 — Code intelligence, symbols and impact graph

- [ ] Index classes, functions, methods, endpoints, tables, migrations and configuration symbols
- [ ] Store symbol purpose, file, dependencies and last-verified commit
- [ ] Detect moved, renamed and deleted symbols
- [ ] Build file-to-symbol and symbol-to-symbol relationships
- [ ] Link symbols to tests, decisions, tasks, services and deployments
- [ ] Provide impact analysis before changes
- [ ] Warn when a requested function or module already exists
- [ ] Provide compact dependency subgraphs for agent context
- [ ] Enforce performance limits for large repositories

## PR #10 — Duplicate and contradiction intelligence

- [ ] Detect exact and semantic duplicate memories
- [ ] Detect duplicate tasks with different wording
- [ ] Detect similar or duplicated code responsibilities
- [ ] Detect duplicate configuration and service registrations
- [ ] Detect conflicting decisions, rules and operational thresholds
- [ ] Return `merge`, `keep_both`, `mark_related`, `replace_old` or `ignore` recommendations
- [ ] Never auto-delete or auto-merge ambiguous records
- [ ] Track superseded decisions while preserving history
- [ ] Add confidence, evidence and human-resolution workflows

## PR #11 — Deployment history and risk-aware execution

- [ ] Persist deployment records by project, service, environment and commit SHA
- [ ] Record tests, result, timestamp, operator and rollback target
- [ ] Compare repository, deployed and remembered commits
- [ ] Classify actions as low, medium or high risk
- [ ] Require stronger confirmation for production, destructive and irreversible actions
- [ ] Validate exact service, host, directory and restart command before execution
- [ ] Detect intent-versus-scope drift after changes
- [ ] Report unexpected files or services touched
- [ ] Provide safe rollback plans and deployment provenance

## PR #12 — Agent evaluation and provenance suite

- [ ] Evaluate project identification accuracy
- [ ] Evaluate service and deployment-target accuracy
- [ ] Measure duplicate-avoidance rate
- [ ] Measure wrong-target prevention rate
- [ ] Measure stale-memory detection rate
- [ ] Measure continuation accuracy across clients and chats
- [ ] Measure token savings under fixed quality thresholds
- [ ] Evaluate prompt-injection and poisoned-memory resistance
- [ ] Add reproducible multi-agent handoff scenarios
- [ ] Explain the source, verification state and confidence of important facts

Core quality metrics:

- project identification accuracy
- service identification accuracy
- duplicate avoidance rate
- wrong-target prevention rate
- context token savings
- task continuation accuracy
- stale-memory detection rate
- contradiction-resolution precision

## PR #13 — Local-first operational dashboard

- [ ] Local dashboard command and localhost-only default
- [ ] Projects and sessions
- [ ] Decisions, tasks, warnings and file memory
- [ ] Search, export and selective deletion
- [ ] Retention, sensitivity and storage visibility
- [ ] Token-budget and estimated-savings analytics
- [ ] Memory verification and staleness status
- [ ] Deployment and risk history
- [ ] SQLite and Supabase backend support

## PR #14 — Galaxy knowledge view

- [ ] Animated project knowledge graph
- [ ] Nodes for projects, files, symbols, decisions, tasks, warnings and sessions
- [ ] Typed relationships and domain clustering
- [ ] Zoom, filters, focus mode and search
- [ ] Select a subgraph to build compact agent context
- [ ] Duplicate, contradiction, stale-memory and orphan-node visualization
- [ ] Performance limits for large graphs

## PR #15 — Teams, roles and remote dashboard

- [ ] Supabase Auth integration
- [ ] Workspace membership and invitations
- [ ] Owner, admin, member and reader roles
- [ ] Shared-project RLS policies
- [ ] Private and shared memories
- [ ] Audit trail and permission tests
- [ ] Secure remote dashboard deployment

## PR #16 — Distribution, deployment and publication

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
- [ ] Automatic cross-client memory recovery
- [ ] Git-grounded stale-memory detection
- [ ] Symbol-level duplicate avoidance and impact analysis
- [ ] Safe project, service and deployment targeting
- [ ] Measurable token savings under fixed quality thresholds
- [ ] Operational dashboard and Galaxy View
- [ ] Export, backup, restore and full-project deletion
