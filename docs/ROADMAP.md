# Persistent Memory MCP delivery roadmap

This roadmap keeps the post-v0.2 work separated into focused, reviewable pull requests.

## PR #2 — Security, isolation and retention

- [x] Secret redaction primitives
- [x] Stored-instruction detection and untrusted-content metadata
- [x] Content-size limits
- [x] Provenance normalization
- [x] TTL/expiry metadata
- [ ] Apply sanitization to every memory write path
- [ ] Enforce project/owner boundary validation in the service layer
- [ ] Add selective forget/delete tools
- [ ] Add retention cleanup and dry-run reporting
- [ ] Add schema columns/indexes for expiry and security metadata
- [ ] Add adversarial and cross-owner isolation tests

## PR #3 — Local SQLite starter mode

- [ ] Storage-adapter interface
- [ ] SQLite schema and migrations
- [ ] Backend selection in `memory-mcp init`
- [ ] Import/export between SQLite and Supabase
- [ ] Backend parity tests

## PR #4 — Safe automatic client installation

- [ ] Detect Codex, Claude Code, OpenCode and Antigravity configuration paths
- [ ] Back up existing files before changes
- [ ] Merge without removing unrelated MCP servers
- [ ] Validate TOML/JSON after writes
- [ ] Add uninstall and rollback commands

## PR #5 — Embeddings and hybrid search

- [ ] Configurable embedding provider
- [ ] Background indexing and reindex command
- [ ] Semantic plus lexical ranking
- [ ] Provider-free fallback
- [ ] Cost, retry and rate-limit controls

## PR #6 — Visual dashboard

- [ ] Projects and sessions
- [ ] Decisions, tasks, warnings and file memory
- [ ] Search, export and selective deletion
- [ ] Retention/storage visibility
- [ ] Authentication boundary for remote deployments

## PR #7 — Teams and roles

- [ ] Supabase Auth integration
- [ ] Workspace membership and invitations
- [ ] Owner, admin and member roles
- [ ] Shared-project RLS policies
- [ ] Audit trail and permission tests

## PR #8 — Distribution and deployment

- [ ] Docker image
- [ ] Render/Railway deployment guides
- [ ] Release automation and package publication
- [ ] MCP Registry submission
- [ ] Versioned upgrade and migration documentation
