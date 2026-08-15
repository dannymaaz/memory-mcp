"""Enrutamiento de modelos segun tarea, limite y contexto disponible."""

from __future__ import annotations

from typing import Any

from persistent_memory_mcp.context_packet import COMPACT_METADATA_BUDGET
from persistent_memory_mcp.tokenization import measure_tokens, resolve_token_counter


class ModelRouter:
    """Selecciona modelos y ajusta contexto de acuerdo con la carga de trabajo."""

    MODEL_STRENGTHS: dict[str, dict[str, Any]] = {
        "gemini-pro": {
            "tasks": {"analysis", "planning", "documentation"},
            "context_limit": 32768,
            "style": "balanced",
        },
        "qwen2.5-coder": {
            "tasks": {"coding", "refactor", "debugging"},
            "context_limit": 65536,
            "style": "code-first",
        },
        "claude-3-7-sonnet": {
            "tasks": {"architecture", "planning", "review"},
            "context_limit": 200000,
            "style": "long-context",
        },
        "gpt-4.1": {
            "tasks": {"reasoning", "review", "multi-step"},
            "context_limit": 131072,
            "style": "deep-reasoning",
        },
    }

    def recommend_model(self, task_type: str) -> str:
        """Recomienda un modelo segun la naturaleza de la tarea."""
        normalized_task = task_type.strip().lower()
        for model_name, settings in self.MODEL_STRENGTHS.items():
            if normalized_task in settings["tasks"]:
                return model_name
        return "gemini-pro"

    def get_context_limit(self, model_name: str) -> int:
        """Obtiene el limite de tokens de contexto de un modelo."""
        return int(
            self.MODEL_STRENGTHS.get(model_name, self.MODEL_STRENGTHS["gemini-pro"])[
                "context_limit"
            ]
        )

    def _refresh_context_packet(self, payload: dict[str, Any]) -> None:
        """Make Context Packet accounting authoritative after delivery annotations."""
        packet = payload.get("context_packet")
        if not isinstance(packet, dict):
            return
        tokens = packet.get("tokens")
        if not isinstance(tokens, dict):
            return
        tokenizer_name = str(tokens.get("tokenizer") or "deterministic")
        model = tokens.get("model")
        if tokenizer_name.startswith("tiktoken:") and model:
            counter = resolve_token_counter(model=str(model), tokenizer="tiktoken")
        else:
            counter = resolve_token_counter(
                model=str(model) if model else None,
                tokenizer=tokenizer_name,
            )

        compact = "estimated_count" not in tokens
        previous: tuple[int, int] | None = None
        for _ in range(8):
            measurement = measure_tokens(payload, counter)
            signature = (measurement.count, measurement.estimated_count)
            if compact:
                tokens["count"] = measurement.count
                tokens["tokenizer"] = measurement.tokenizer
                tokens["mode"] = "exact" if measurement.exact else "estimated"
                if measurement.model:
                    tokens["model"] = measurement.model
            else:
                tokens.update(measurement.as_dict())
            if signature == previous:
                break
            previous = signature
        final = measure_tokens(payload, counter)
        if compact:
            tokens["count"] = final.count
            tokens["tokenizer"] = final.tokenizer
            tokens["mode"] = "exact" if final.exact else "estimated"
            if final.model:
                tokens["model"] = final.model
        else:
            tokens.update(final.as_dict())
        budget = int(tokens.get("budget") or 0)
        if budget and final.count > budget:
            raise ValueError(
                f"final routed Context Packet exceeds token budget: {final.count} > {budget}"
            )

    def optimize_context_for_model(
        self,
        model_name: str,
        context: dict[str, Any],
        estimated_tokens: int,
    ) -> dict[str, Any]:
        """Marca estrategia de compresion y prioridad por modelo."""
        limit = self.get_context_limit(model_name)
        ratio = 0 if limit == 0 else min(1.0, estimated_tokens / limit)
        optimized = dict(context)
        optimized["model"] = model_name
        packet = optimized.get("context_packet")
        packet_tokens = packet.get("tokens") if isinstance(packet, dict) else None
        packet_budget = (
            int(packet_tokens.get("budget") or 0) if isinstance(packet_tokens, dict) else 0
        )
        style = self.MODEL_STRENGTHS.get(model_name, {}).get("style", "balanced")
        if packet_budget and packet_budget <= COMPACT_METADATA_BUDGET:
            optimized["delivery_profile"] = {"style": style}
        else:
            optimized["delivery_profile"] = {
                "style": style,
                "estimated_tokens": estimated_tokens,
                "limit": limit,
                "compression_level": "high" if ratio > 0.8 else "low",
            }
        self._refresh_context_packet(optimized)
        return optimized
