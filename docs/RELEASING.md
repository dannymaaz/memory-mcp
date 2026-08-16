# Releasing Persistent Memory MCP

This document is the release-operator checklist for v0.3.0 and later local-first releases.

## Release policy

A release is publishable only when the **exact candidate commit and exact distribution files** have passed the applicable validation gates. Do not publish from an unvalidated local working tree and do not rebuild distributions between GitHub Release verification and PyPI publication.

Required evidence includes Ubuntu/Windows/macOS testing on Python 3.11–3.13, lint/compile, agent regressions, dependency audit, wheel/sdist build, `twine check`, clean installation, installed v0.2.0 upgrade validation, and SHA-256 generation/verification.

## v0.3.0 immutable release source

The only valid `v0.3.0` tag target is:

```text
9e0a084dd9b179612082edef99e1c3c9bf563ffa
```

That commit is the validated merge of PR #89 into `release/v0.3.0-final`. It preserves the v0.3.0 feature set, constrains MCP to `mcp>=1.28,<2`, uses the real v1 `FastMCP` implementation, and passed Quality #361.

Current `main` contains post-v0.3 MCP v2 work and is intentionally not the v0.3.0 release source.

## GitHub Release v0.3.0 — complete

PR #103 added `.github/workflows/publish-github-v0.3.0.yml`, passed Quality #401 with 16/16 jobs, and merged as:

```text
4fff71ec44a40d7d4d296d4ad0b30d39583ea8f3
```

Publisher run `31979169557` completed successfully. It validated the immutable source, built and checked the release artifacts, created the annotated tag, created a draft Release, re-downloaded and revalidated the draft assets, and only then made the Release final.

Verified state:

- annotated `v0.3.0` resolves exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- GitHub Release is final and non-prerelease;
- Release URL: https://github.com/dannymaaz/memory-mcp/releases/tag/v0.3.0;
- exact assets:
  - `persistent_memory_mcp-0.3.0-py3-none-any.whl`;
  - `persistent_memory_mcp-0.3.0.tar.gz`;
  - `SHA256SUMS`.

The one-time branch trigger used by the connected GitHub app has been retired. The GitHub Release publisher is manual again and intentionally refuses to overwrite the already-published v0.3.0 Release.

## Existing tag-push validation workflow

`.github/workflows/release.yml` remains a validation workflow for future externally-created `v*` tags. It verifies tag/package-version agreement, builds wheel/sdist, checks metadata and checksums, validates clean installation and the installed upgrade path, and retains the validated bundle as an Actions artifact.

For v0.3.0, the canonical GitHub Release evidence is publisher run `31979169557` and the final Release linked above.

## Artifact checksums

`SHA256SUMS` is a hard publication gate. Verification uses:

```bash
python scripts/generate_checksums.py dist --verify
```

A checksum mismatch, missing distribution or unexpected checksum entry is a hard stop.

Do not rebuild v0.3.0 distributions after the final GitHub Release. PyPI must receive the exact wheel/sdist already attached to that Release.

## PyPI Trusted Publishing — next external gate

The PyPI publication workflow is `.github/workflows/publish-pypi.yml` and uses the GitHub environment name `pypi`.

Configure the Trusted Publisher on PyPI with exactly:

- **Owner:** `dannymaaz`
- **Repository:** `memory-mcp`
- **Workflow filename:** `publish-pypi.yml`
- **Environment:** `pypi`

The workflow grants `id-token: write` only to the publication job and uses PyPI Trusted Publishing/OIDC rather than a long-lived API token.

For v0.3.0 it fails closed unless:

- the trigger is explicitly authorized for v0.3.0;
- a final non-draft, non-prerelease GitHub Release exists;
- `v0.3.0` resolves exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- the release contains the expected wheel, sdist and `SHA256SUMS`;
- checksum verification passes;
- artifact metadata identifies v0.3.0;
- `twine check` passes.

Only the verified wheel/sdist are transferred to the isolated OIDC publication job. The package is **not rebuilt** between GitHub Release and PyPI.

### Starting the PyPI workflow

Two tightly scoped trigger paths are supported:

1. **GitHub UI:** run **Publish v0.3.0 to PyPI** manually with `release_tag=v0.3.0`.
2. **Connected GitHub app:** after Trusted Publisher is configured, create the exact branch `release/publish-pypi-v0.3.0` from the validated current `main`. A push to any other branch cannot trigger PyPI publication.

Do **not** create the connector trigger branch before the PyPI Trusted Publisher is configured. Branch creation itself can generate the push event, so no extra trigger commit is required.

## Public PyPI validation

After publication, validate from a clean environment rather than the repository checkout:

```bash
python -m venv .venv-release-check
# activate the environment for the current shell
python -m pip install --upgrade pip
python -m pip install persistent-memory-mcp==0.3.0
memory-mcp --help
memory-mcp doctor
```

Then run the documented disposable local init/status/health/migration-preview path before marking PyPI publication complete.

## MCP Registry preparation

Submit/update Registry metadata only after the GitHub Release and PyPI package are public and stable.

Initial metadata:

- package: `persistent-memory-mcp`;
- command: `memory-mcp`;
- transport: stdio;
- Python: 3.11+;
- default backend: local SQLite;
- optional remote extras: Supabase/PostgreSQL;
- scope: personal local-first memory server;
- stable local `OWNER_ID` required;
- `MEMORY_CONFIRMATION_SECRET` used for destructive-operation confirmations;
- Dashboard remains localhost-only;
- destructive operations remain explicit and backup-first.

Do not present team workspaces, shared roles or a public collaborative dashboard as supported capabilities.

## Completion checklist

The v0.3.0 release record is complete only after all of the following are true:

- [x] final GitHub Release exists for annotated `v0.3.0` → `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- [x] wheel, sdist and `SHA256SUMS` are verified release assets;
- [ ] PyPI Trusted Publisher is configured;
- [ ] `.github/workflows/publish-pypi.yml` succeeds for v0.3.0;
- [ ] clean public PyPI install/smoke test succeeds;
- [ ] MCP Registry metadata is submitted/updated;
- [ ] GitHub Issue #53 and the Notion release record contain final PyPI/Registry evidence.

## Rollback

Rollback instructions are maintained in `docs/UPGRADING.md`. Never copy a live WAL database file as a recovery procedure. Stop clients, verify the backup manifest, use SQLite's backup API to restore, verify integrity, then downgrade the package.
