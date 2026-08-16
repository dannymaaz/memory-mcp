# Application composition and MCP Tool Registry

Persistent Memory MCP composes its runtime explicitly before starting the MCP transport. The composition layer is intentionally incremental: it makes initialization order visible and centralizes tool registration for integrations that need dynamic replacement, without rewriting the existing server or changing public tool contracts.

## Composition root

`persistent_memory_mcp.application.create_application(settings)` is the runtime composition root.

It returns an `Application` object containing:

- the validated `RuntimeSettings`;
- the imported server module;
- the shared `ToolRegistry` attached to that server module;
- the explicit integration installation order.

Construction and transport startup are separate:

```python
settings = RuntimeSettings.from_env()
application = create_application(settings)
application.run()
```

`create_application()` does not call `server.main()` by itself. This keeps composition testable and prevents transport startup while architecture tests inspect the assembled runtime.

## Initialization order

The canonical order is exposed as `APPLICATION_INTEGRATION_ORDER`:

1. `deployment_storage`
2. `security_boundaries`
3. `hybrid_search`
4. `embedding_lifecycle`
5. `duplicate_intelligence`
6. `deployment_risk`
7. `agent_evaluation`
8. `confirmed_deletion`
9. `verified_restore`
10. `git_verification`
11. `code_intelligence`
12. `progressive_retrieval`
13. `symbol_evolution`
14. `paginated_reads`
15. `continuation_contract`
16. `session_lifecycle`

Two ordering constraints are especially important.

### Deployment storage before server import

The deployment-storage extension is installed before `src.server` is imported by the normal runtime path. This preserves the historical assumption that local storage capabilities are available before the server creates its first client.

### Continuation before Session Lifecycle

`continuation_contract` must wrap `end_session` before `session_lifecycle` captures it. That ensures:

- explicit session close;
- cross-interface handoff;
- idle expiry

all persist the same Continuation Contract rather than diverging through different close paths.

Tests assert the exact order and this relative dependency.

## Migration readiness

The SQLite migration guard now belongs to the composition layer as `assert_migration_ready(settings)`.

For an existing SQLite database with pending migrations, the runtime still fails closed and instructs the user to review/apply migrations explicitly. The MCP server never mutates an existing stale schema automatically during startup.

`persistent_memory_mcp.runtime._assert_migration_ready` remains as a backward-compatible private alias for existing tests/importers while the implementation lives in the composition layer.

## Tool Registry

`persistent_memory_mcp.tool_registry.ToolRegistry` provides a single deterministic registration path for integrations migrated to it.

For a tool registration, the registry synchronizes the surfaces that the repository currently supports:

- module attribute, such as `server_module.plan_memory_restore`;
- existing `server._tools` entry when present;
- existing `server._tool_manager._tools` entry when present;
- legacy `TOOL_HANDLERS` mapping when present;
- legacy `TOOL_SCHEMAS` list when present.

If a tool does not already exist, the registry calls the server's public/decorator-style `tool(name=..., description=...)` registration entry point. A missing/non-callable registration API or a decorator that raises is treated as a hard registration error.

The registry does **not** require every server implementation to expose private registration dictionaries after a successful decorator call. Some supported adapters/fakes do not make registration observable through those internals; successful decorator execution is therefore sufficient when no prior tool can be replaced directly.

## Idempotency

`get_tool_registry(server_module)` attaches one registry instance to the server module and reuses it on subsequent calls.

The registry:

- replaces existing callbacks instead of blindly adding duplicates;
- collapses duplicate legacy schema entries by tool name;
- updates the description on the retained schema entry;
- keeps one in-memory `ToolRegistration` per public tool name.

Integrations also retain their historical installed flags. Repeated `create_application()` calls against the same server module therefore do not duplicate Restore/Deletion tools or schemas.

## Integrations migrated in PR #79

The first slice migrates only the two integrations that duplicated nearly identical private registry mutation helpers:

- `install_confirmed_deletion()`;
- `install_verified_restore()`.

Both accept an optional shared `registry=` parameter. Calls that do not supply it remain compatible because each installer falls back to `get_tool_registry(server_module)`.

The business logic is unchanged:

- deletion still uses its signed preview/confirmation contract and shared single-use fingerprint set;
- restore still uses verified preview/confirmation, safety backup, atomic replacement, post-validation and rollback;
- public tool names and arguments are unchanged.

## Failure behavior

The composition/registry layer is intended to make failures visible rather than silently swallow architecture errors.

Examples that fail explicitly:

- no MCP `server` object on the server module;
- no callable `server.tool(...)` when a required tool must be newly registered;
- registration decorator creation or execution raises;
- existing SQLite database has pending migrations.

Tool business functions continue to preserve their existing user-facing error payload behavior; this refactor changes assembly, not domain semantics.

## MCP package compatibility boundary

CI currently installs the repository's declared `mcp>=0.1.0` dependency, which resolves to MCP 2.0.0. During PR #79, validation revealed that `src.server` still imports `mcp.server.fastmcp.FastMCP`; that module path is absent in the installed 2.0.0 package, so the repository currently selects its minimal local fallback server class.

That compatibility problem is tracked separately in **Issue #81**. PR #79 intentionally does not mix an upstream MCP API migration with the application-composition refactor.

Until Issue #81 is resolved, Tool Registry tests validate both generic registration surfaces and the server class that this repository actually selects at runtime.

## Non-goals of this slice

PR #79 does not:

- migrate every integration to `ToolRegistry`;
- change SQLite schema or migrations;
- change backend defaults;
- change any public tool name or domain contract;
- replace `src.server` wholesale;
- migrate the project to a new MCP major-version API;
- add remote/public administration;
- alter destructive confirmation semantics.

Future registry migrations should be small, individually tested changes rather than one broad server rewrite.
