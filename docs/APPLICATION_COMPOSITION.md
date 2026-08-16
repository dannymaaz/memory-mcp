# Application composition and MCP Tool Registry

This document describes the runtime composition boundary introduced for MEM-29 / Issue #75. The change is intentionally incremental: it does not rewrite the legacy server, change public MCP tool contracts, or expand the product beyond its local-first operating model.

## Serve lifecycle

`memory-mcp serve` now follows one explicit path:

1. Load `.env` values.
2. Build immutable `RuntimeSettings`.
3. Refuse startup when an existing SQLite database has pending migrations.
4. Call `create_application(settings)`.
5. Run the composed MCP server.

`create_application(settings)` is the composition root. It owns integration ordering and returns an `Application` containing the active settings, legacy server module, and shared `ToolRegistry`.

## Initialization order

The order is a runtime contract and is exposed as `INITIALIZATION_ORDER` for regression tests:

1. Deployment storage extension.
2. Security boundaries.
3. Hybrid search.
4. Embedding lifecycle.
5. Duplicate intelligence.
6. Deployment risk.
7. Agent evaluation.
8. Confirmed deletion.
9. Verified restore.
10. Git verification.
11. Code intelligence.
12. Progressive retrieval.
13. Symbol evolution.
14. Paginated reads.
15. Continuation contract.
16. Session lifecycle.

Continuation must wrap `end_session` before Session Lifecycle captures it. This preserves the existing behavior for explicit closes, handoffs, and idle expiry.

## ToolRegistry contract

Dynamic integrations must register tools through `persistent_memory_mcp.tool_registry.ToolRegistry` instead of maintaining their own copies of FastMCP mutation logic.

The registry keeps these surfaces synchronized when they exist:

- the FastMCP tool registration surface;
- existing FastMCP `_tools` / `_tool_manager._tools` entries when replacing an already registered callable;
- `src.server.TOOL_HANDLERS`, used by local dispatch/tests;
- `src.server.TOOL_SCHEMAS`, used by local discovery/tests;
- the corresponding function attribute on `src.server`.

Registration is idempotent by tool name. Existing entries are replaced in place rather than appended again, and schema metadata is updated without creating duplicate schema rows.

A new tool is registered through FastMCP's public `tool(...)` decorator. If that API is unavailable or registration raises, composition fails with a clear `RuntimeError`; required tools are no longer silently dropped.

## First migrated integrations

This slice migrates the two maintenance-sensitive integrations called out by MEM-29:

- `install_confirmed_deletion(...)`;
- `install_verified_restore(...)`.

Their public tool names, arguments, confirmation behavior, and return payloads are unchanged. Both installers keep their previous direct-call compatibility and accept the shared registry only as an optional integration argument.

## Idempotent application construction

The composed `Application` is stored on the server module. Repeating `create_application(...)` with the same immutable settings returns the existing application and does not reinstall tools. Attempting to recompose the same process with different settings fails explicitly instead of leaving a partially reconfigured global server.

## Scope boundary

This architecture work does not introduce:

- remote dashboard exposure;
- multi-user roles or team management;
- automatic destructive maintenance;
- automatic schema migration on serve;
- changes to the SQLite/Supabase/PostgreSQL storage contracts.

The dashboard and maintenance surfaces remain localhost/local-first unless a separate, reviewed product decision changes that boundary.
