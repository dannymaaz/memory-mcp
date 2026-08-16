# Releasing Persistent Memory MCP

This document is the release operator checklist for v0.3.0 and later local-first releases.

## Release policy

A release is publishable only when the **exact candidate commit and exact distribution files** have passed the applicable validation gates. Do not publish from an unvalidated local working tree and do not rebuild distributions between GitHub Release verification and PyPI publication.

Required evidence includes:

- Ubuntu, Windows and macOS tests on Python 3.11, 3.12 and 3.13;
- lint and compile checks;
- agent evaluation regressions;
- dependency audit including optional remote extras;
- wheel and sdist build plus `twine check`;
- clean wheel installation on Ubuntu, Windows and macOS;
- installed CLI smoke tests;
- real installed v0.2.0 → candidate upgrade validation on all three operating systems;
- SHA-256 checksum generation and verification for final artifacts.

## v0.3.0 immutable release source

The validated v0.3.0 release preparation PR is #54. Its merge commit is:

```text
4dc160c1fdf0e2858337239c42c9085fe8097493
```

That commit reports package version `0.3.0` and contains the tag-triggered `.github/workflows/release.yml`. The final PR #54 head passed Quality #209 before merge.

**Do not create `v0.3.0` from current `main`.** Current `main` contains later post-v0.3 work. The release tag must resolve to the validated release commit above.

## v0.3.0 release checklist

1. Confirm the target commit is exactly `4dc160c1fdf0e2858337239c42c9085fe8097493`.
2. Confirm that commit reports `version = "0.3.0"` in `pyproject.toml`.
3. Confirm `CHANGELOG.md` and `docs/UPGRADING.md` describe the exact release behavior.
4. Confirm README, ROADMAP, IMPLEMENTATION_STATUS and Notion agree on delivered/partial/out-of-scope capabilities.
5. Create annotated tag `v0.3.0` from the validated release commit.
6. Let `.github/workflows/release.yml` build wheel/sdist from that tag, run release validation and generate `SHA256SUMS`.
7. Require the tag workflow to succeed before creating a GitHub Release.
8. Download the retained workflow bundle and verify every artifact against `SHA256SUMS`.
9. Create the GitHub Release with title `Persistent Memory MCP v0.3.0 — Data Safety and Recovery` and attach exactly:
   - the validated wheel;
   - the validated sdist;
   - `SHA256SUMS`.
10. Configure the PyPI Trusted Publisher described below.
11. Run `.github/workflows/publish-pypi.yml` manually with `release_tag=v0.3.0`.
12. The workflow must download the GitHub Release assets, verify the release/tag/commit, verify SHA-256 and package metadata, and publish those exact distributions without rebuilding them.
13. In a clean environment, install `persistent-memory-mcp==0.3.0` from public PyPI and repeat the basic `init`, `doctor`, `status`, `health` and migration-preview smoke tests.
14. Submit/update MCP Registry metadata only after the public package and GitHub Release URLs are stable.
15. Mark the Notion release record complete with GitHub Release, PyPI and Registry evidence.

## Tag release workflow

`.github/workflows/release.yml` runs only on `v*` tag pushes. For the tag commit it:

- verifies tag/package-version agreement;
- builds wheel and sdist;
- runs `twine check` and release-version validation;
- generates and verifies `SHA256SUMS`;
- validates a clean installed wheel;
- revalidates the installed v0.2.0 upgrade path;
- retains the validated bundle as a GitHub Actions artifact.

The workflow does **not** publish to PyPI and does not create the final GitHub Release automatically.

## GitHub Release notes

Use the v0.3.0 section of `CHANGELOG.md` as the source of truth. The release must explicitly call out:

- SQLite-first local scope;
- explicit migration requirement for existing 0.2.0 databases;
- backup/health/restore/migration safety foundation;
- cross-platform validation;
- known partial areas;
- out-of-scope collaborative/team features.

## Artifact checksums

The release build generates a standard `SHA256SUMS` file covering the wheel and sdist only. Verify it before upload and again before PyPI publication:

```bash
python scripts/generate_checksums.py dist --verify
```

A checksum mismatch, missing distribution or unexpected checksum entry is a hard stop.

## PyPI Trusted Publishing

The repository publication workflow is `.github/workflows/publish-pypi.yml`. It is intentionally **manual** and uses a protected GitHub environment named `pypi`.

Configure the Trusted Publisher on PyPI with these exact values:

- **Owner:** `dannymaaz`
- **Repository:** `memory-mcp`
- **Workflow filename:** `publish-pypi.yml`
- **Environment:** `pypi`

The workflow grants `id-token: write` only to the publication job and does not use a long-lived PyPI username/password/API token. The GitHub environment should use protection rules/manual approval where available.

For v0.3.0, the workflow additionally fails closed unless:

- input tag is exactly `v0.3.0`;
- a non-draft, non-prerelease GitHub Release for that tag exists;
- checkout of that tag resolves exactly to `4dc160c1fdf0e2858337239c42c9085fe8097493`;
- release assets include the expected wheel, sdist and `SHA256SUMS`;
- checksum verification passes;
- artifact metadata identifies as v0.3.0;
- `twine check` passes.

Only the verified wheel/sdist are transferred to the isolated OIDC publication job. The publication job uses PyPA's `gh-action-pypi-publish` Trusted Publishing flow and does not rebuild the package.

## Public PyPI validation

After a successful publication, verify from a clean environment rather than the repository checkout:

```bash
python -m venv .venv-release-check
# activate the environment for the current shell
python -m pip install --upgrade pip
python -m pip install persistent-memory-mcp==0.3.0
memory-mcp --help
memory-mcp doctor
```

Then run the documented local init/status/health/migration-preview smoke path against disposable data before marking PyPI publication complete.

## MCP Registry preparation

For the initial Registry submission:

- package name: `persistent-memory-mcp`;
- canonical command: `memory-mcp`;
- transport: stdio;
- Python: 3.11+;
- default backend: local SQLite;
- advanced remote extras: optional Supabase/PostgreSQL;
- product scope: personal local-first memory server;
- required configuration: stable local `OWNER_ID`; use `MEMORY_CONFIRMATION_SECRET` for destructive-operation confirmations;
- public documentation: repository documentation site and README;
- security behavior: localhost-only Dashboard, scoped memory operations, explicit destructive confirmations, backup-first migration and restore workflows.

Do not describe team workspaces, shared roles or a remote collaborative dashboard as supported product capabilities.

## Rollback

Release rollback instructions are maintained in `docs/UPGRADING.md`. Never advise copying a live WAL database file as the recovery procedure. Stop clients, verify the backup manifest, use SQLite's backup API to restore, verify integrity, then downgrade the package.
