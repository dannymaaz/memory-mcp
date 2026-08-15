# Releasing Persistent Memory MCP

This document is the release operator checklist for v0.3.0 and later local-first releases.

## Release policy

A release is publishable only when the exact candidate commit has passed:

- Ubuntu, Windows and macOS tests on Python 3.11, 3.12 and 3.13;
- lint and compile checks;
- agent evaluation regressions;
- dependency audit including optional remote extras;
- wheel and sdist build plus `twine check`;
- clean wheel installation on Ubuntu, Windows and macOS;
- installed CLI smoke tests;
- real installed v0.2.0 → candidate upgrade validation on all three operating systems;
- SHA-256 checksum generation for final artifacts.

Do not publish from an unvalidated local working tree.

## v0.3.0 release checklist

1. Confirm `pyproject.toml` reports `0.3.0`.
2. Confirm `CHANGELOG.md` and `docs/UPGRADING.md` describe the exact release behavior.
3. Confirm README, ROADMAP, IMPLEMENTATION_STATUS and Notion agree on delivered/partial/out-of-scope capabilities.
4. Run the Quality workflow on the release PR and require all jobs to succeed.
5. Merge the release PR into `main`.
6. Create annotated tag `v0.3.0` from the validated merge commit.
7. Let the tag release workflow build wheel/sdist from that exact commit and generate `SHA256SUMS`.
8. Verify every artifact against `SHA256SUMS` before publication.
9. Create the GitHub Release using the v0.3.0 section of `CHANGELOG.md` and attach:
   - wheel;
   - sdist;
   - `SHA256SUMS`.
10. Validate PyPI metadata with `twine check` and publish the exact same wheel/sdist through PyPI Trusted Publishing or another configured secure publication method.
11. In a clean environment, install `persistent-memory-mcp==0.3.0` from PyPI and repeat the basic `init`, `doctor`, `status`, `health` and migration-preview smoke tests.
12. Update the MCP Registry submission metadata/docs only after the public package and release URLs are stable.
13. Mark the Notion release record complete with the GitHub Release, PyPI and Registry evidence.

## GitHub Release notes

Use `CHANGELOG.md` as the source of truth. The release title should be:

```text
Persistent Memory MCP v0.3.0 — Data Safety and Recovery
```

The release must explicitly call out:

- SQLite-first local scope;
- explicit migration requirement for existing 0.2.0 databases;
- backup/health/restore/migration safety foundation;
- cross-platform validation;
- known partial areas;
- out-of-scope collaborative/team features.

## Artifact checksums

The release build generates a standard `SHA256SUMS` file. Verify it from the artifact directory before upload:

```bash
python scripts/generate_checksums.py dist --verify
```

The checksum manifest covers the wheel and sdist only and must not include itself.

## PyPI preparation

The project metadata already exposes the repository, documentation and issue URLs. Before publication verify:

```bash
python -m build
python -m twine check dist/*
python scripts/generate_checksums.py dist --verify
```

Recommended publication is PyPI Trusted Publishing from GitHub Actions, so no long-lived PyPI token needs to be stored in the repository. Trusted Publishing must be configured in PyPI before enabling an automated publish step.

Until that external trust relationship is configured and verified, the release workflow should build and retain artifacts but must not attempt to publish them.

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
- security behavior: localhost-only dashboard, scoped memory operations, explicit destructive confirmations, backup-first migration and restore workflows.

Do not describe team workspaces, shared roles or a remote collaborative dashboard as supported product capabilities.

## Rollback

Release rollback instructions are maintained in `docs/UPGRADING.md`. Never advise copying a live WAL database file as the recovery procedure. Stop clients, verify the backup manifest, use SQLite's backup API to restore, verify integrity, then downgrade the package.
