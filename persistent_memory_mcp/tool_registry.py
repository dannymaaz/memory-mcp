"""Deterministic, idempotent registration for dynamically installed MCP tools."""

from __future__ import annotations

from typing import Any, Callable

ToolCallable = Callable[..., Any]


class ToolRegistry:
    """Keep MCPServer, local dispatch helpers, and schemas in sync.

    Integrations use this registry instead of mutating MCP SDK internals. MCP v2
    exposes public ``add_tool`` and ``remove_tool`` methods, so replacements use
    those APIs directly. The local handler/schema mirrors remain the source of
    truth for whether a tool is already known to this application.
    """

    def __init__(self, server_module: Any) -> None:
        self.server_module = server_module
        self.server = getattr(server_module, "server", None)
        if self.server is None:
            raise RuntimeError("MCP Tool Registry requires server_module.server")

    def register(
        self,
        name: str,
        description: str,
        function: ToolCallable,
    ) -> ToolCallable:
        """Register or replace one tool without private MCP SDK access."""
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("tool name must not be empty")
        if not callable(function):
            raise TypeError(f"tool {normalized_name!r} must be callable")

        add_tool = getattr(self.server, "add_tool", None)
        if not callable(add_tool):
            raise RuntimeError(
                f"cannot register MCP tool {normalized_name!r}: "
                "MCPServer.add_tool API is unavailable"
            )

        if self._is_known(normalized_name):
            remove_tool = getattr(self.server, "remove_tool", None)
            if not callable(remove_tool):
                raise RuntimeError(
                    f"cannot replace MCP tool {normalized_name!r}: "
                    "MCPServer.remove_tool API is unavailable"
                )
            try:
                remove_tool(normalized_name)
            except Exception as exc:
                raise RuntimeError(
                    f"failed to remove existing MCP tool {normalized_name!r}"
                ) from exc

        try:
            add_tool(function, name=normalized_name, description=description)
        except Exception as exc:
            raise RuntimeError(
                f"failed to register MCP tool {normalized_name!r}"
            ) from exc

        setattr(self.server_module, normalized_name, function)
        self._sync_handler(normalized_name, function)
        self._sync_schema(normalized_name, description)
        return function

    def _is_known(self, name: str) -> bool:
        """Return whether the application already tracks a registered tool."""
        handlers = getattr(self.server_module, "TOOL_HANDLERS", None)
        if isinstance(handlers, dict) and name in handlers:
            return True

        schemas = getattr(self.server_module, "TOOL_SCHEMAS", None)
        if isinstance(schemas, list):
            return any(
                isinstance(schema, dict) and schema.get("name") == name
                for schema in schemas
            )
        return False

    def _sync_handler(self, name: str, function: ToolCallable) -> None:
        handlers = getattr(self.server_module, "TOOL_HANDLERS", None)
        if handlers is None:
            return
        if not isinstance(handlers, dict):
            raise RuntimeError("server_module.TOOL_HANDLERS must be a dict when present")
        handlers[name] = function

    def _sync_schema(self, name: str, description: str) -> None:
        schemas = getattr(self.server_module, "TOOL_SCHEMAS", None)
        if schemas is None:
            return
        if not isinstance(schemas, list):
            raise RuntimeError("server_module.TOOL_SCHEMAS must be a list when present")

        for schema in schemas:
            if isinstance(schema, dict) and schema.get("name") == name:
                schema["description"] = description
                return
        schemas.append({"name": name, "description": description})