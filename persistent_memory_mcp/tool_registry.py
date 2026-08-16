"""Explicit idempotent MCP tool registration for composed integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

ToolFunction = Callable[..., Any]


class ToolRegistryError(RuntimeError):
    """Raised when a required MCP tool cannot be registered safely."""


@dataclass(frozen=True)
class ToolRegistration:
    """One deterministic public tool registration."""

    name: str
    description: str
    function: ToolFunction


class ToolRegistry:
    """Synchronize one tool across module, FastMCP and legacy compatibility registries."""

    def __init__(self, server_module: Any) -> None:
        server = getattr(server_module, "server", None)
        if server is None:
            raise ToolRegistryError("server module does not expose an MCP server")
        self.server_module = server_module
        self.server = server
        self._registrations: dict[str, ToolRegistration] = {}

    @property
    def registrations(self) -> tuple[ToolRegistration, ...]:
        return tuple(self._registrations[name] for name in sorted(self._registrations))

    def register(
        self,
        name: str,
        description: str,
        function: ToolFunction,
    ) -> ToolFunction:
        """Register or replace a tool without creating duplicate public entries."""
        tool_name = str(name or "").strip()
        tool_description = str(description or "").strip()
        if not tool_name:
            raise ToolRegistryError("tool name is required")
        if not tool_description:
            raise ToolRegistryError(f"description is required for tool {tool_name}")
        if not callable(function):
            raise ToolRegistryError(f"tool {tool_name} must be callable")

        setattr(self.server_module, tool_name, function)
        found_existing, introspectable = self._replace_existing(tool_name, function)
        if not found_existing:
            factory = getattr(self.server, "tool", None)
            if not callable(factory):
                raise ToolRegistryError(
                    f"MCP server cannot register required tool {tool_name}: tool() is unavailable"
                )
            try:
                decorator = factory(name=tool_name, description=tool_description)
                if not callable(decorator):
                    raise TypeError("tool() did not return a decorator")
                decorator(function)
            except Exception as exc:
                raise ToolRegistryError(
                    f"MCP server could not register required tool {tool_name}"
                ) from exc
            if introspectable and not self._is_registered(tool_name):
                raise ToolRegistryError(
                    f"MCP server did not retain required tool {tool_name} after registration"
                )

        handlers = getattr(self.server_module, "TOOL_HANDLERS", None)
        if isinstance(handlers, dict):
            handlers[tool_name] = function

        schemas = getattr(self.server_module, "TOOL_SCHEMAS", None)
        if isinstance(schemas, list):
            matches = [item for item in schemas if isinstance(item, dict) and item.get("name") == tool_name]
            if matches:
                matches[0]["description"] = tool_description
                for duplicate in matches[1:]:
                    schemas.remove(duplicate)
            else:
                schemas.append({"name": tool_name, "description": tool_description})

        registration = ToolRegistration(tool_name, tool_description, function)
        self._registrations[tool_name] = registration
        return function

    def _replace_existing(self, name: str, function: ToolFunction) -> tuple[bool, bool]:
        found = False
        introspectable = False

        tools = getattr(self.server, "_tools", None)
        if isinstance(tools, dict):
            introspectable = True
            if name in tools:
                tools[name] = function
                found = True

        manager = getattr(self.server, "_tool_manager", None)
        managed = getattr(manager, "_tools", None)
        if isinstance(managed, dict):
            introspectable = True
            if name in managed:
                existing = managed[name]
                try:
                    if hasattr(existing, "fn"):
                        existing.fn = function
                    elif hasattr(existing, "function"):
                        existing.function = function
                    else:
                        managed[name] = function
                except (AttributeError, TypeError):
                    managed[name] = function
                found = True

        return found, introspectable

    def _is_registered(self, name: str) -> bool:
        tools = getattr(self.server, "_tools", None)
        if isinstance(tools, dict) and name in tools:
            return True
        manager = getattr(self.server, "_tool_manager", None)
        managed = getattr(manager, "_tools", None)
        return isinstance(managed, dict) and name in managed


def get_tool_registry(server_module: Any) -> ToolRegistry:
    """Return the single registry attached to one server module."""
    existing = getattr(server_module, "_memory_mcp_tool_registry", None)
    if isinstance(existing, ToolRegistry) and existing.server_module is server_module:
        return existing
    registry = ToolRegistry(server_module)
    setattr(server_module, "_memory_mcp_tool_registry", registry)
    return registry
