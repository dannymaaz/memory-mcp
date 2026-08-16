# MCP SDK compatibility boundary

Persistent Memory MCP `main` uses the MCP Python SDK **v2 MCPServer API**. The supported dependency range for post-v0.3 development is:

```text
mcp>=2,<3
```

The runtime imports the installed SDK directly:

```python
from mcp.server import MCPServer
```

There is no local MCP fallback in packaged runtime operation. An absent or incompatible SDK must fail explicitly rather than silently selecting a different server implementation.

## Runtime contract

The post-v0.3 runtime keeps these invariants:

- `src.server.MCPServer` is the installed `mcp.server.MCPServer` class;
- `src.server.server` is an instance of that installed SDK class;
- public MCP tool names, arguments and return payloads remain unchanged;
- the packaged entrypoint continues to run the server with `transport="stdio"`;
- the Application composition root and its initialization order remain unchanged;
- Continuation Contract still wraps `end_session` before Session Lifecycle captures it;
- local-first SQLite behavior, Dashboard/Galaxy exposure and destructive confirmation semantics are unchanged.

## Tool Registry contract

`persistent_memory_mcp.tool_registry.ToolRegistry` no longer reaches into MCP SDK private registration structures.

New tools are registered through the public MCP v2 API:

```python
server.add_tool(function, name=name, description=description)
```

Known tools are replaced deterministically by calling `remove_tool(name)` followed by `add_tool(...)`. The application's `TOOL_HANDLERS` and `TOOL_SCHEMAS` mirrors determine whether a tool is already known, so replacement does not depend on `_tools` or `_tool_manager` internals.

Compatibility regressions exercise the real installed `MCPServer` with its public `list_tools()` and `call_tool()` methods to prove that replacement changes both the advertised description and the callable executed by the server.

## Version and release boundary

This migration is **post-v0.3 mainline work**. It does not rewrite the immutable v0.3.0 release candidate tracked by Issue #53. That release target remains bound to the dependency/runtime state that was validated for the release candidate.

A later release cut from `main` will carry the MCP v2 dependency policy.

## Validation requirements

Before the MCP v2 migration can be considered complete, all of the following must pass on the exact PR head:

1. MCP SDK v2 installs on Python 3.11, 3.12 and 3.13;
2. compile and Ruff checks pass;
3. full pytest and agent-evaluation regressions pass on Ubuntu, Windows and macOS;
4. real `MCPServer` tool listing/calling and replacement tests pass;
5. clean wheel/sdist installation passes on all supported operating systems;
6. installed v0.2.0 upgrade validation remains green;
7. dependency audit and reference quality gates remain green.

## Scope

The MCP v2 migration does not change:

- database schema or migrations;
- storage/backend behavior;
- public MCP tool contracts;
- Dashboard/Galaxy behavior;
- backup/restore/deletion confirmation rules;
- local-first product scope.