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

**Do not create `v0.3.0` from current `main` and do not use the superseded `4dc160c…` candidate.** Current `main` contains post-v0.3 MCP v2 work.

## Preferred v0.3.0 GitHub Release path

Use `.github/workflows/publish-github-v0.3.0.yml` from `main` after its validating PR is merged.

The workflow is deliberately manual. In GitHub Actions, select **Publish GitHub Release v0.3.0**, choose **Run workflow**, and enter the exact confirmation:

```text
RELEASE-v0.3.0
```

The workflow then performs the complete GitHub-side publication gate in one run:

1. checks out `9e0a084dd9b179612082edef99e1c3c9bf563ffa`, never current `main`;
2. verifies package version `0.3.0`, the MCP v1 dependency boundary and the `FastMCP` release implementation;
3. refuses to overwrite an existing GitHub Release;
4. if `v0.3.0` already exists, requires it to be an **annotated tag** resolving exactly to the immutable release SHA;
5. builds wheel and sdist from the immutable source;
6. runs `twine check`, release-version validation, checksum generation/verification, clean-wheel validation and the installed v0.2.0 upgrade regression;
7. extracts the canonical v0.3.0 release notes from `CHANGELOG.md`;
8. retains the validated bundle as a GitHub Actions artifact;
9. creates the annotated `v0.3.0` tag only after the build/validation gate has passed, when the tag is absent;
10. creates a **draft** GitHub Release with exactly the validated wheel, sdist and `SHA256SUMS`;
11. re-downloads those draft assets from GitHub and verifies their checksums, package version and metadata;
12. compares the re-downloaded checksum manifest with the locally validated manifest;
13. only after those checks pass, converts the draft into the final, non-prerelease GitHub Release;
14. verifies the final release state and exact three-asset bundle.

The workflow has `contents: write` because it must create the annotated tag and GitHub Release. It uses only the repository-scoped `GITHUB_TOKEN`; no PAT is required.

### Why this is one workflow

GitHub intentionally prevents most events created with a workflow's `GITHUB_TOKEN` from starting another workflow. Therefore a tag created inside the manual publisher cannot be relied on to trigger the separate tag-push workflow. The guarded publisher performs build, tag and GitHub Release creation itself rather than depending on a silent second trigger.

## Existing tag-push validation workflow

`.github/workflows/release.yml` remains available for a tag created outside Actions. On a `v*` tag push it:

- verifies tag/package-version agreement;
- builds wheel and sdist;
- runs `twine check` and release-version validation;
- generates and verifies `SHA256SUMS`;
- validates a clean installed wheel;
- revalidates the installed v0.2.0 upgrade path;
- retains the validated bundle as a GitHub Actions artifact.

It does **not** create a GitHub Release or publish to PyPI. For v0.3.0, prefer the guarded manual publisher above so the release source and asset handoff are enforced in one audited run.

## Manual fallback

If the guarded GitHub Release workflow cannot run because of repository Actions permissions, use this fallback only after confirming the immutable SHA:

1. create annotated `v0.3.0` at `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
2. let `.github/workflows/release.yml` finish successfully;
3. download its retained bundle;
4. verify `SHA256SUMS` locally;
5. create the GitHub Release titled `Persistent Memory MCP v0.3.0 — Data Safety and Recovery` with exactly the validated wheel, sdist and `SHA256SUMS`;
6. continue with PyPI Trusted Publishing below.

Never recreate artifacts after the GitHub Release has been established.

## GitHub Release notes

The v0.3.0 section of `CHANGELOG.md` is the source of truth. The title is:

```text
Persistent Memory MCP v0.3.0 — Data Safety and Recovery
```

The notes must communicate SQLite-first local scope, explicit migration for existing 0.2.0 databases, backup/health/restore/migration safety, MCP SDK v1 compatibility (`mcp>=1.28,<2`), cross-platform validation, known partial areas and intentionally out-of-scope collaborative/team features.

## Artifact checksums

The release build generates `SHA256SUMS` for the wheel and sdist. Verification is a hard gate:

```bash
python scripts/generate_checksums.py dist --verify
```

A checksum mismatch, missing distribution or unexpected checksum entry is a hard stop.

## PyPI Trusted Publishing

The PyPI publication workflow is `.github/workflows/publish-pypi.yml`. It is manual and uses the protected GitHub environment `pypi`.

Configure the Trusted Publisher on PyPI with exactly:

- **Owner:** `dannymaaz`
- **Repository:** `memory-mcp`
- **Workflow filename:** `publish-pypi.yml`
- **Environment:** `pypi`

The workflow grants `id-token: write` only to the publication job and uses PyPI Trusted Publishing/OIDC rather than a long-lived API token.

For v0.3.0 it fails closed unless:

- input tag is exactly `v0.3.0`;
- a final non-draft, non-prerelease GitHub Release exists;
- that tag resolves exactly to `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- the release contains the expected wheel, sdist and `SHA256SUMS`;
- checksum verification passes;
- artifact metadata identifies v0.3.0;
- `twine check` passes.

Only the verified wheel/sdist are transferred to the isolated OIDC publication job. The package is **not rebuilt** between GitHub Release and PyPI.

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

- [ ] final GitHub Release exists for annotated `v0.3.0` → `9e0a084dd9b179612082edef99e1c3c9bf563ffa`;
- [ ] wheel, sdist and `SHA256SUMS` are verified release assets;
- [ ] PyPI Trusted Publisher is configured;
- [ ] `.github/workflows/publish-pypi.yml` succeeds for `release_tag=v0.3.0`;
- [ ] clean public PyPI install/smoke test succeeds;
- [ ] MCP Registry metadata is submitted/updated;
- [ ] GitHub Issue #53 and the Notion release record contain final public evidence.

## Rollback

Rollback instructions are maintained in `docs/UPGRADING.md`. Never copy a live WAL database file as a recovery procedure. Stop clients, verify the backup manifest, use SQLite's backup API to restore, verify integrity, then downgrade the package.
