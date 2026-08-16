"""Deterministic, idempotent registration for dynamically installed MCP tools."""

from __future__ import annotations

from typing import Any, Callable

ToolCallable = Callable[..., Any]


class ToolRegistry:
    """Keep FastMCP, local dispatch helpers, and schemas in sync.

    Integrations should use this registry instead of mutating FastMCP internals
    independently. Existing tools are replaced in place when a known registry
    surface is available; new tools are registered through FastMCP's public
    ``tool`` decorator. Registration failures are explicit rather than silently
    ignored.
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
        """Register or replace one tool without creating duplicate entries."""
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("tool name must not be empty")
        if not callable(function):
            raise TypeError(f"tool {normalized_name!r} must be callable")

        replaced = self._replace_existing(normalized_name, function)
        if not replaced:
            tool_decorator = getattr(self.server, "tool", None)
            if not callable(tool_decorator):
                raise RuntimeError(
                    f"cannot register MCP tool {normalized_name!r}: "
                    "FastMCP tool registration API is unavailable"
                )
            try:
                tool_decorator(name=normalized_name, description=description)(function)
            except Exception as exc:
                raise RuntimeError(
                    f"failed to register MCP tool {normalized_name!r}"
                ) from exc

        setattr(self.server_module, normalized_name, function)
        self._sync_handler(normalized_name, function)
        self._sync_schema(normalized_name, description)
        return function

    def _replace_existing(self, name: str, function: ToolCallable) -> bool:
        """Replace an already-registered callable on known FastMCP surfaces."""
        replaced = False

        tools = getattr(self.server, "_tools", None)
        if isinstance(tools, dict) and name in tools:
            tools[name] = function
            replaced = True

        manager = getattr(self.server, "_tool_manager", None)
        managed = getattr(manager, "_tools", None)
        if isinstance(managed, dict) and name in managed:
            tool = managed[name]
            try:
                if hasattr(tool, "fn"):
                    tool.fn = function
                elif hasattr(tool, "function"):
                    tool.function = function
                else:
                    managed[name] = function
            except Exception as exc:
                raise RuntimeError(
                    f"failed to replace existing MCP tool {name!r}"
                ) from exc
            replaced = True

        return replaced

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
