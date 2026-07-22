"""Context optimization for interfaces with different memory limits."""

from __future__ import annotations

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

    def trim_context(
        self,
        context: dict[str, Any],
        max_tokens: int,
        *,
        intent: str = "",
        layer: str = "detailed",
    ) -> dict[str, Any]:
        """Build ranked context that remains inside a fixed token budget."""
        return build_context(
            context,
            intent=intent,
            layer=layer,
            budget=max_tokens,
        ).context

    def optimize_for_interface(
        self,
        context: dict[str, Any],
        interface_name: str,
        *,
        intent: str = "",
        layer: str = "operational",
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Optimize context for one consumer interface and annotate strategy."""
        interface_key = interface_name.strip().lower() or "native"
        limit = int(
            max_tokens
            or self.INTERFACE_LIMITS.get(interface_key, self.INTERFACE_LIMITS["native"])
        )
        result = build_context(
            context,
            intent=intent,
            layer=layer,
            budget=limit,
        )
        optimized = dict(result.context)
        optimized["interface"] = interface_key
        optimized["token_estimate"] = result.metrics.returned_tokens
        optimized["strategy"] = {
            "limit": limit,
            "layer": result.layer,
            "intent": intent,
            "focus": (
                "code"
                if interface_key in {"opencode", "claude-code", "qwen-code", "codex"}
                else "reasoning"
            ),
            "saved_tokens": result.metrics.saved_tokens,
            "savings_percent": result.metrics.savings_percent,
        }
        return optimized
