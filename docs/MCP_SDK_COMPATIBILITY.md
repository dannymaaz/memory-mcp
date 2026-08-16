# MCP SDK compatibility boundary

Persistent Memory MCP currently implements its server against the MCP Python SDK **v1 FastMCP API**. The supported dependency range for this implementation is therefore:

```text
mcp>=1.28,<2
```

This upper bound is intentional and temporary. It prevents an incompatible MCP v2 installation from silently selecting the repository's minimal local fallback server.

## Why the bound is required

`src.server` currently imports:

```python
from mcp.server.fastmcp import FastMCP
```

MCP Python SDK v2 changed the high-level server API and no longer exposes that v1 import path. Before PR #85, the unconstrained dependency `mcp>=0.1.0` resolved to MCP 2.x. The broad `ModuleNotFoundError` fallback in `src.server` then treated the moved API as if MCP were not installed and constructed the repository's fallback server instead.

That behavior was unsafe from a compatibility perspective because package installation succeeded while the runtime silently used a different server implementation.

## Current contract

PR #85 restores an explicit relationship between code and dependency:

- install MCP SDK v1.28 or newer within the v1 major line;
- `src.server.FastMCP` must be the installed `mcp.server.fastmcp.FastMCP`;
- `src.server.server` must be an instance of that installed SDK class;
- the MEM-29 `ToolRegistry` must register and replace tools against the installed FastMCP implementation;
- wheel/sdist clean installation and the v0.2.0 upgrade regression must resolve the same supported range.

CI has a dedicated compatibility regression for these invariants.

## Why PR #85 does not migrate directly to MCP v2

MEM-29 / PR #80 only recently introduced the explicit Application composition root and Tool Registry. A major MCP server migration would require validating the v2 server constructor, registration/replacement API, Tool Registry behavior and stdio transport together.

Combining those changes with the dependency repair would make it harder to distinguish a packaging regression from a server-API migration regression.

Issue #88 therefore owns the deliberate v2 migration.

## MCP v2 follow-up

Issue #88 must complete these steps before the `<2` upper bound is removed:

1. migrate `src.server` to the supported MCP v2 high-level server API;
2. adapt Tool Registry to prefer supported v2 registration/replacement APIs;
3. prove the runtime uses the installed v2 server rather than a fallback;
4. preserve public MCP tool names, arguments, payloads and stdio behavior;
5. narrow or remove the broad fallback so an installed-but-incompatible SDK cannot be mistaken for an absent dependency;
6. pass the full Ubuntu/Windows/macOS × Python 3.11–3.13 Quality matrix;
7. pass clean wheel install and installed v0.2.0 upgrade validation;
8. only then widen the package dependency to the validated v2-compatible range.

## Fallback policy

The local fallback in `src.server` is not a substitute for normal packaged operation. Packaged/CI operation must use the declared MCP SDK dependency. Any future fallback retention should be explicit, test-only/development-oriented and must not mask an installed dependency with an incompatible API.

## Scope

This compatibility repair does not change:

- database schema or migrations;
- storage/backend behavior;
- public MCP tool contracts;
- Dashboard/Galaxy exposure;
- destructive confirmation semantics;
- local-first product scope.
