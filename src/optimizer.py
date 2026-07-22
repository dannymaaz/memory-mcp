"""Context optimization for interfaces with different memory limits."""

from __future__ import annotations

import os
from typing import Any

from persistent_memory_mcp.context_engine import build_context, estimate_tokens


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
        return build_context(
            context,
            intent=resolved_intent,
            layer=resolved_layer,
            budget=max_tokens,
            include_untrusted=resolved_untrusted,
        ).context

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
        result = build_context(
            context,
            intent=resolved_intent,
            layer=resolved_layer,
            budget=limit,
            include_untrusted=resolved_untrusted,
        )
        optimized = dict(result.context)
        optimized["interface"] = interface_key
        optimized["token_estimate"] = result.metrics.returned_tokens
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
            "saved_tokens": result.metrics.saved_tokens,
            "savings_percent": result.metrics.savings_percent,
            "compressed_items": result.metrics.compressed_items,
        }
        return optimized
