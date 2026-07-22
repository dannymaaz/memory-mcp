"""Context optimization for interfaces with different memory limits."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from persistent_memory_mcp.context_engine import build_context, estimate_tokens
from persistent_memory_mcp.project_guardrails import compact_guardrails


class ContextOptimizer:
    """Compress and prioritize persistent context for multi-interface agents."""

    INTERFACE_LIMITS = {
        "native": 24000,
        "opencode": 48000,
        "claude-code": 56000,
        "qwen-code": 32000,
        "codex": 64000,
    }

    def estimate_tokens(self, payload: Any) -> int:
        """Estimate tokens without requiring a provider tokenizer."""
        return estimate_tokens(payload)

    def _prepare_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Attach compact critical rules to the always-loaded project block."""
        prepared = dict(context)
        manifest = prepared.get("project_guardrails")
        if isinstance(manifest, dict):
            project = dict(prepared.get("project") or {})
            project["guardrails"] = compact_guardrails(manifest)
            prepared["project"] = project
        return prepared

    def _essential_metadata(self, context: Mapping[str, Any]) -> dict[str, Any]:
        """Keep only server-control metadata that must survive optimization."""
        metadata = context.get("metadata")
        if not isinstance(metadata, Mapping):
            return {}
        allowed = {
            "interface",
            "recommended_model",
            "repo",
            "retention_policy",
            "project_id",
            "workspace_id",
        }
        return {
            key: metadata[key]
            for key in allowed
            if key in metadata and metadata[key] not in (None, "", [], {})
        }

    def _resolve_options(
        self,
        context: dict[str, Any],
        *,
        intent: str,
        layer: str,
        max_tokens: int | None,
        include_untrusted: bool,
    ) -> tuple[str, str, int | None, bool]:
        request = context.get("context_request")
        request_options = request if isinstance(request, dict) else {}
        resolved_intent = intent or str(
            request_options.get("intent") or os.getenv("MEMORY_CONTEXT_INTENT", "")
        )
        resolved_layer = str(
            request_options.get("layer")
            or os.getenv("MEMORY_CONTEXT_LAYER")
            or layer
        ).strip().lower()
        raw_budget = request_options.get("budget") or os.getenv("MEMORY_CONTEXT_BUDGET")
        resolved_budget = max_tokens
        if resolved_budget is None and raw_budget not in (None, ""):
            resolved_budget = int(raw_budget)
        raw_untrusted = request_options.get("include_untrusted")
        if raw_untrusted is None:
            raw_untrusted = os.getenv("MEMORY_CONTEXT_INCLUDE_UNTRUSTED", "false")
        resolved_untrusted = include_untrusted or str(raw_untrusted).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return resolved_intent, resolved_layer, resolved_budget, resolved_untrusted

    def _optimize(
        self,
        context: dict[str, Any],
        *,
        intent: str,
        layer: str,
        limit: int,
        include_untrusted: bool,
    ) -> tuple[dict[str, Any], Any]:
        """Build context while reserving space for essential server metadata."""
        prepared = self._prepare_context(context)
        metadata = self._essential_metadata(prepared)
        metadata_payload = {"metadata": metadata} if metadata else {}
        reserve = estimate_tokens(metadata_payload) + (4 if metadata else 0)
        engine_limit = max(128, limit - reserve)
        result = build_context(
            prepared,
            intent=intent,
            layer=layer,
            budget=engine_limit,
            include_untrusted=include_untrusted,
        )
        optimized = dict(result.context)
        if metadata:
            optimized["metadata"] = metadata

        # A very small user budget may leave insufficient room for metadata.
        # Remove lowest-priority selected items until the complete response fits.
        removable_fields = (
            "timeline",
            "sessions",
            "checkpoints",
            "file_memory",
            "files",
            "decisions",
            "tasks",
            "warnings",
        )
        while estimate_tokens(optimized) > limit:
            removed = False
            for field in removable_fields:
                values = optimized.get(field)
                if isinstance(values, list) and values:
                    values.pop()
                    if not values:
                        optimized.pop(field, None)
                    removed = True
                    break
            if not removed:
                break
        return optimized, result

    def trim_context(
        self,
        context: dict[str, Any],
        max_tokens: int,
        *,
        intent: str = "",
        layer: str = "detailed",
        include_untrusted: bool = False,
    ) -> dict[str, Any]:
        """Build ranked context that remains inside a fixed token budget."""
        resolved_intent, resolved_layer, _, resolved_untrusted = self._resolve_options(
            context,
            intent=intent,
            layer=layer,
            max_tokens=max_tokens,
            include_untrusted=include_untrusted,
        )
        optimized, _ = self._optimize(
            context,
            intent=resolved_intent,
            layer=resolved_layer,
            limit=max_tokens,
            include_untrusted=resolved_untrusted,
        )
        return optimized

    def optimize_for_interface(
        self,
        context: dict[str, Any],
        interface_name: str,
        *,
        intent: str = "",
        layer: str = "operational",
        max_tokens: int | None = None,
        include_untrusted: bool = False,
    ) -> dict[str, Any]:
        """Optimize context for one consumer interface and annotate strategy."""
        interface_key = interface_name.strip().lower() or "native"
        resolved_intent, resolved_layer, requested_budget, resolved_untrusted = self._resolve_options(
            context,
            intent=intent,
            layer=layer,
            max_tokens=max_tokens,
            include_untrusted=include_untrusted,
        )
        limit = int(
            requested_budget
            or self.INTERFACE_LIMITS.get(interface_key, self.INTERFACE_LIMITS["native"])
        )
        optimized, result = self._optimize(
            context,
            intent=resolved_intent,
            layer=resolved_layer,
            limit=limit,
            include_untrusted=resolved_untrusted,
        )
        optimized["interface"] = interface_key
        optimized["token_estimate"] = estimate_tokens(optimized)
        guardrails_loaded = bool(
            isinstance(optimized.get("project"), dict)
            and optimized["project"].get("guardrails")
        )
        optimized["strategy"] = {
            "limit": limit,
            "layer": result.layer,
            "intent": resolved_intent,
            "include_untrusted": resolved_untrusted,
            "focus": (
                "code"
                if interface_key in {"opencode", "claude-code", "qwen-code", "codex"}
                else "reasoning"
            ),
            "saved_tokens": max(0, estimate_tokens(context) - estimate_tokens(optimized)),
            "savings_percent": round(
                max(0, estimate_tokens(context) - estimate_tokens(optimized))
                / max(1, estimate_tokens(context))
                * 100,
                2,
            ),
            "compressed_items": result.metrics.compressed_items,
            "guardrails_loaded": guardrails_loaded,
        }
        return optimized
