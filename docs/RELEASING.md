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

Do not publish from an unvalidated local working tree and do not rebuild distributions between release verification and external publication.

## v0.3.0 compatibility boundary

The v0.3.0 runtime uses the MCP Python SDK v1 `mcp.server.fastmcp.FastMCP` API. The release therefore constrains the SDK to `mcp>=1.28,<2`. MCP v2 uses a different high-level server API and must be adopted in a separate, explicitly validated migration rather than during the v0.3.0 release.

The original prepared release merge `4dc160c1fdf0e2858337239c42c9085fe8097493` is the content baseline, but it is **not** the final tag target because it allowed an unconstrained MCP dependency. The final v0.3.0 tag target is the merge commit produced by the release-only compatibility PR into `release/v0.3.0-final`, after the exact-head Quality gate passes.

Do not tag current `main`: it contains later post-v0.3 product work that is intentionally excluded from this release.

## v0.3.0 release checklist

1. Confirm `pyproject.toml` reports `0.3.0` and constrains MCP to `mcp>=1.28,<2`.
2. Confirm the release compatibility regression proves `src.server.server` is the real installed `mcp.server.fastmcp.FastMCP`, not the local fallback.
3. Confirm `CHANGELOG.md` and `docs/UPGRADING.md` describe the exact release behavior.
4. Run the Quality workflow on the release-only PR and require all jobs to succeed on its exact HEAD.
5. Merge that PR into `release/v0.3.0-final`; record the resulting merge SHA as the immutable release commit.
6. Update the guarded PyPI publication workflow on `main` so its expected commit equals that immutable release SHA, then validate and merge that workflow separately.
7. Create annotated tag `v0.3.0` from the immutable `release/v0.3.0-final` merge commit — not from `main` and not from the original `4dc160c...` baseline.
8. Let the tag release workflow build wheel/sdist from that exact commit and generate `SHA256SUMS`.
9. Require the tag workflow to succeed and verify every artifact against `SHA256SUMS` before publication.
10. Create the GitHub Release using the v0.3.0 section of `CHANGELOG.md` and attach exactly:
   - the validated wheel;
   - the validated sdist;
   - `SHA256SUMS`.
11. Configure the repository's PyPI Trusted Publisher and run the guarded manual publication workflow from `main` with `release_tag=v0.3.0`.
12. That publication workflow must download and verify the exact GitHub Release assets; it must not rebuild the package.
13. In a clean environment, install `persistent-memory-mcp==0.3.0` from public PyPI and repeat the basic `init`, `doctor`, `status`, `health` and migration-preview smoke tests.
14. Update the MCP Registry submission metadata/docs only after the public package and release URLs are stable.
15. Mark the Notion release record complete with the GitHub Release, PyPI and Registry evidence.

## GitHub Release notes

Use `CHANGELOG.md` as the source of truth. The release title should be:

```text
Persistent Memory MCP v0.3.0 — Data Safety and Recovery
```

The release must explicitly call out:

- SQLite-first local scope;
- explicit migration requirement for existing 0.2.0 databases;
- backup/health/restore/migration safety foundation;
- supported MCP SDK v1 compatibility range for this release;
- cross-platform validation;
- known partial areas;
- out-of-scope collaborative/team features.

## Artifact checksums

The release build generates a standard `SHA256SUMS` file. Verify it from the artifact directory before upload:

```bash
python scripts/generate_checksums.py dist --verify
```

The checksum manifest covers the wheel and sdist only and must not include itself. A mismatch, missing distribution or unexpected checksum entry is a hard stop.

## PyPI preparation

The project metadata already exposes the repository, documentation and issue URLs. The publication path on `main` uses PyPI Trusted Publishing/OIDC so a long-lived PyPI token does not need to be stored in the repository.

The guarded publisher must fail closed unless the requested GitHub Release/tag is `v0.3.0`, the tag resolves to the recorded immutable release commit, the release is final rather than draft/prerelease, checksums match and package metadata identifies as v0.3.0.

Until that trust relationship and exact release bundle are configured and verified, the release artifacts must not be published to PyPI.

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
