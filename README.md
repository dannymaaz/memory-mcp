<p align="center"><img src="docs/assets/logo.svg" alt="Persistent Memory MCP logo" width="132"></p>

<h1 align="center">Persistent Memory MCP</h1>
<p align="center"><strong>Your coding tools forget. Persistent Memory MCP remembers.</strong></p>
<p align="center">Local-first persistent project memory and context compilation for MCP-compatible development agents.</p>

<p align="center">
  <a href="https://dannymaaz.github.io/memory-mcp/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/ROADMAP.md">Roadmap</a> ·
  <a href="docs/IMPLEMENTATION_STATUS.md">Implementation status</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

![Version](https://img.shields.io/badge/version-0.3.0-0A7D73)
![License](https://img.shields.io/badge/license-MIT-black)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-v1.28%2B%20%3C2-6C5CE7)
![Storage](https://img.shields.io/badge/storage-local%20SQLite-003B57?logo=sqlite&logoColor=white)

> **Release status — 2026-08-16:** v0.3.0 has a fully validated immutable release candidate, but the public GitHub Release and PyPI publication are still pending. Until PyPI publication is verified, install from this repository instead of assuming `pipx install persistent-memory-mcp` is available publicly. See [Releasing](docs/RELEASING.md) and [Issue #53](https://github.com/dannymaaz/memory-mcp/issues/53).

## What is Persistent Memory MCP?

Persistent Memory MCP is an open-source Model Context Protocol server that gives coding assistants durable, searchable project memory. It stores architecture, technical decisions, tasks, warnings, repository evidence, checkpoints and continuation state so compatible clients can resume work without reconstructing the project from scratch.

The product is intentionally **personal and local-first**:

- one local installation;
- SQLite by default;
- localhost-only Dashboard and Galaxy UI;
- explicit owner/project isolation;
- no automatic execution of repository code;
- optional self-managed Supabase/PostgreSQL adapters;
- no hosted team workspace, public collaborative dashboard or SaaS role hierarchy.

## Core capabilities

| Capability | What it provides |
|---|---|
| Durable project memory | Decisions, tasks, warnings, checkpoints, sessions and file context survive client restarts |
| Git-aware context | Bind memory and repository evidence to repository, branch and commit state |
| Context Packet v1 | Versioned, provenance-aware context under a hard token budget |
| Progressive retrieval | Expand repository map → files → symbols → exact fragments instead of loading whole repos |
| Persistent symbol evolution | Track logical symbols across commits, moves and conservative rename matches |
| Context-quality gates | Detect retrieval, token-budget, provenance and safety regressions in CI |
| Operational map / Galaxy | Inspect bounded owner-scoped project risk and evidence relationships |
| Automatic continuation | Persist bounded resume-ready state for close, handoff and idle expiry |
| Deterministic pagination | Stable owner/project-scoped keyset pagination with bounded cursors |
| Verified backup | WAL-safe SQLite backup with integrity validation and SHA-256 manifest |
| Health diagnostics | Read-only SQLite integrity, foreign-key, disk and backup-readiness checks |
| Confirmed restore | Preview → signed confirmation → safety backup → atomic restore → verification/rollback |
| Versioned migrations | Explicit, backup-first, checksum-verified schema upgrades |
| Confirmed deletion | Exact scoped preview plus short-lived single-use confirmation |
| Private Dashboard | Localhost-only operational and maintenance UI |
| Application composition | Explicit `create_application(settings)` runtime composition boundary |
| Idempotent MCP Tool Registry | Centralized dynamic tool registration/replacement without duplicate schemas |

## Quick start

### 1. Install from the repository

Public PyPI publication is not yet complete. Use the validated source tree for now:

```bash
git clone https://github.com/dannymaaz/memory-mcp.git
cd memory-mcp
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

For a non-editable installation from the repository:

```bash
pip install "git+https://github.com/dannymaaz/memory-mcp.git"
```

After v0.3.0 is published and publicly smoke-tested on PyPI, the intended package command is:

```bash
pipx install persistent-memory-mcp
```

Do not rely on that PyPI command until [Issue #53](https://github.com/dannymaaz/memory-mcp/issues/53) records successful public installation evidence.

### 2. Initialize the local installation

```bash
memory-mcp init
```

The normal local database is:

```text
~/.memory-mcp/memory.db
```

### 3. Check the installation

```bash
memory-mcp doctor
memory-mcp status
memory-mcp health
```

For full SQLite integrity validation:

```bash
memory-mcp health --full
```

### 4. Register it in an MCP client

```json
{
  "mcpServers": {
    "persistent-memory-mcp": {
      "command": "memory-mcp",
      "env": {
        "MEMORY_BACKEND": "sqlite",
        "OWNER_ID": "your-stable-local-identifier",
        "MEMORY_CONFIRMATION_SECRET": "your-private-confirmation-secret"
      }
    }
  }
}
```

The server uses stdio when launched by an MCP client. It can also be started manually:

```bash
memory-mcp serve
```

## Optional storage adapters

SQLite is the default and recommended local path. Remote adapters are opt-in and self-managed:

```bash
pip install -e ".[supabase]"
pip install -e ".[postgresql]"
```

These adapters do not change the product into a hosted multi-user service.

## MCP SDK compatibility

The current runtime uses the MCP Python SDK v1 `FastMCP` API and intentionally constrains the dependency to:

```text
mcp>=1.28,<2
```

Issue #88 tracks a deliberate future migration to MCP v2 `MCPServer`. The upper bound must not be removed until that migration passes the same cross-platform and installed-package gates.

## Context Compiler

The completed Context Compiler phase adds five evidence-driven layers:

1. **Context Packet + token accounting** — PR #60 / Quality #226.
2. **Progressive repository retrieval** — PR #62 / Quality #235.
3. **Persistent code provenance/symbol evolution** — PR #64 / Quality #250.
4. **Context-quality and adversarial regression gates** — PR #66 / Quality #262.
5. **Operational project map / risk-oriented Galaxy** — PR #68 / Quality #282.

See:

- [Context quality](docs/CONTEXT_QUALITY.md)
- [Operational map](docs/OPERATIONAL_MAP.md)
- [Continuation contract](docs/CONTINUATION.md)
- [Pagination](docs/PAGINATION.md)
- [Application composition](docs/APPLICATION_COMPOSITION.md)

## Data-safety model

Persistent Memory MCP treats destructive local operations as explicit workflows, not hidden maintenance:

- migrations are previewed and applied explicitly;
- existing stale schemas fail closed on serve rather than auto-migrating;
- restore requires a signed plan tied to the exact backup state;
- restore creates a verified safety backup immediately before replacement;
- deletion requires an exact preview and short-lived single-use confirmation;
- backup verification uses SHA-256 manifests without storing memory contents in the manifest;
- Dashboard maintenance remains bound to localhost.

See [Upgrading](docs/UPGRADING.md), [Releasing](docs/RELEASING.md) and [Security Policy](SECURITY.md).

## Upgrading from 0.2.0

Version 0.3.0 introduces explicit versioned SQLite migrations. Existing databases are never silently migrated on MCP startup.

Preview first:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env
```

Apply only after reviewing the plan:

```bash
memory-mcp-migrate --env ~/.memory-mcp/.env --apply --yes
```

The apply step creates a verified pre-migration backup before mutation. Keep the backup and its JSON manifest until the upgraded installation has been verified.

## v0.3.0 release chain

The public v0.3.0 release must be created from the immutable release-only commit:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

That commit was produced by PR #89 after Quality #361 passed the complete Ubuntu/Windows/macOS × Python 3.11–3.13 release matrix, release artifact checks and installed v0.2.0 upgrade validation.

Current `main` includes later post-v0.3 work and **must not** be tagged as v0.3.0.

The repository-side PyPI workflow was merged in PR #91 after Quality #368. It requires the future `v0.3.0` GitHub Release to resolve exactly to the immutable release commit, downloads its wheel/sdist/`SHA256SUMS`, verifies them and publishes those exact distributions through PyPI Trusted Publishing without rebuilding them.

Remaining release operations are tracked in [Issue #53](https://github.com/dannymaaz/memory-mcp/issues/53).

## Development validation

The Quality workflow covers:

- Ubuntu, Windows and macOS;
- Python 3.11, 3.12 and 3.13;
- compile and Ruff lint checks;
- unit/integration tests;
- agent evaluation regressions;
- Context Compiler reference gates;
- dependency audit including optional extras;
- wheel/sdist build and metadata validation;
- SHA-256 release checksums;
- clean wheel installation;
- installed v0.2.0 → candidate upgrade validation.

Run the core local checks with:

```bash
python -m compileall persistent_memory_mcp src tests
ruff check .
pytest -q
```

## Documentation

- [Public documentation](https://dannymaaz.github.io/memory-mcp/)
- [Roadmap](docs/ROADMAP.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Release process](docs/RELEASING.md)
- [Upgrade and rollback](docs/UPGRADING.md)
- [Application composition](docs/APPLICATION_COMPOSITION.md)
- [Dashboard maintenance](docs/DASHBOARD_MAINTENANCE.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Security

Do not report suspected vulnerabilities in a public issue. Follow [SECURITY.md](SECURITY.md) for private reporting guidance.

## Contributing

Contributions are welcome when they preserve the local-first safety boundary and include appropriate deterministic tests. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
