# Deterministic keyset pagination

Persistent Memory MCP uses bounded **keyset pagination** for high-volume local SQLite reads instead of offset-based traversal or loading full result sets into Python.

This contract was introduced by MEM-30 / Issue #72 and is used by local MCP history reads and Dashboard drill-down endpoints.

## Why keyset pagination

Offset pagination becomes progressively more expensive on large tables and can produce unstable traversal when rows are inserted between page requests. The local pagination contract instead orders by a deterministic timestamp plus `id` and carries the last boundary in an opaque cursor.

The historical `SQLiteStorage.select()` method remains available for compatibility. New high-volume product paths should use `SQLiteStorage.select_page()`.

## Storage page contract

A page contains:

```json
{
  "items": [],
  "next_cursor": "<opaque cursor or null>",
  "has_more": true,
  "limit": 50,
  "order_by": "created_at",
  "descending": true,
  "cursor_version": 1
}
```

Defaults and bounds:

- default page size: **50**;
- hard maximum page size: **200**;
- default stable order: `(created_at, id)` descending;
- ascending traversal is supported;
- order columns are allow-listed and must also exist in the target SQLite table;
- filter columns are validated against the real table schema before SQL interpolation.

## Cursor binding

The cursor is URL-safe, opaque to callers and versioned. It contains a bounded continuation boundary plus a SHA-256 query fingerprint.

The fingerprint binds the cursor to:

- table;
- exact filters;
- order column;
- direction;
- cursor contract version.

Using a cursor with another owner/project scope, table, sort direction or filter set fails closed with `InvalidCursorError`. Malformed or unsupported-version cursors also fail closed.

The cursor is a pagination continuation token, **not an authentication credential**. Owner/project authorization remains enforced independently by the product read path.

## Stable traversal anchor

On the first SQLite page, the implementation captures the maximum matching internal SQLite `rowid` and stores that anchor only inside the opaque cursor.

All later pages require `rowid <= anchor` in addition to the keyset boundary. This means rows inserted after page 1 do not enter an already-started traversal even if they share the same timestamp or would otherwise sort ahead of the current boundary.

A fresh traversal sees the new records.

The anchor is not returned as a public response field and callers must not depend on its representation.

## Same-timestamp behavior

`id` is the mandatory tie-breaker. Regressions explicitly exercise thousands of rows with the **same timestamp**, proving that pages do not duplicate or skip records merely because timestamps collide.

For normal memory tables, `created_at` is preferred because it is intended to be immutable. Product integrations should avoid mutable ordering columns when a stable creation timestamp exists.

## MCP history reads

The local SQLite runtime exposes:

- `get_project_timeline(..., cursor=...)` — backward-compatible timeline response plus `returned_count`, `has_more`, `next_cursor` and `cursor_version`;
- `list_project_history_page(...)` — generic bounded history page for:
  - timeline;
  - sessions;
  - checkpoints;
  - tasks;
  - warnings;
  - decisions.

These reads are scoped by both `owner_id` and `project_id` and use the same `SQLiteStorage.select_page()` implementation.

The legacy remote adapter behavior remains unchanged when no cursor is supplied. Keyset cursor traversal currently requires the local SQLite backend rather than pretending that the remote adapters implement identical semantics.

## Dashboard drill-down

The localhost Dashboard retains its existing bounded multi-table snapshot as the overview. High-volume collection traversal is available through:

```text
/api/table-page?table=tasks&project_id=<project>&limit=50
```

A subsequent request supplies the returned `cursor`.

The endpoint:

- is read-only and localhost-only through the existing Dashboard server;
- resolves or requires one active owner and fails closed when multiple owners exist without configuration;
- verifies that a requested project belongs to that owner before reading project-scoped tables;
- accepts only known Dashboard tables that are also supported by the local SQLite adapter;
- returns total count, returned count, `has_more` and the next opaque cursor;
- applies recursive secret redaction before returning records;
- preserves existing Dashboard security headers.

The Dashboard search field `q` remains part of the bounded overview snapshot. It is intentionally not mixed into `/api/table-page` so a cursor does not pretend that Python-side partial candidate filtering is a complete full-text traversal.

## Secret handling

Pagination exposed a useful hardening case: a JSON mapping such as `{"token": "secret-value"}` may not match a provider-specific token pattern.

`redact_sensitive_value()` therefore also redacts values under exact credential-bearing mapping keys such as:

- `token` / `access_token` / `refresh_token`;
- `password` / `passwd`;
- `api_key` / `apikey`;
- `secret`;
- `authorization`;
- `credential` / `credentials`;
- `private_key`.

Unrelated metric names such as `token_count` are not redacted.

## Reproducible evaluation

`scripts/evaluate_storage_pagination.py` builds a local, non-sensitive SQLite fixture containing:

- **10,000** records in the active owner/project scope;
- **200** foreign-owner records;
- identical timestamps for all focus records;
- page size **200**;
- one new focus record inserted after the first page.

The gate requires:

- exactly 10,000 original records traversed;
- zero duplicates;
- no foreign-owner records;
- exactly 50 pages;
- the post-start insert excluded from the active traversal;
- that insert visible to a fresh traversal;
- total traversal ≤ **5,000 ms**;
- every page ≤ **1,000 ms**.

Initial Ubuntu reference evidence before final documentation synchronization:

| Metric | Observed |
|---|---:|
| Records traversed | **10,000** |
| Pages | **50** |
| Mean page latency | **13.79 ms** |
| Maximum page latency | **19.77 ms** |
| Total traversal latency | **692.30 ms** |

These timings are regression-fixture observations from hosted CI, not production SLA claims. The thresholds are intentionally much wider so normal hosted-runner variance does not create flaky builds while pathological growth still blocks CI.

## Local reproduction

```bash
python scripts/evaluate_storage_pagination.py
```

The evaluation is provider-free and does not execute repository code.
