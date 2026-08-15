"""Local token accounting with optional model-aware reference tokenizers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

DETERMINISTIC_TOKENIZER_NAME = "deterministic-char4-v1"
DEFAULT_TIKTOKEN_ENCODING = "o200k_base"


class TokenizerUnavailableError(RuntimeError):
    """Raised when an explicitly requested tokenizer is not installed or resolvable."""


@runtime_checkable
class TokenCounter(Protocol):
    """Minimal token counter contract used by the context compiler."""

    name: str
    model: str | None
    exact: bool

    def count(self, payload: Any) -> int:
        """Count serialized tokens for one payload."""


def serialize_for_tokens(payload: Any) -> str:
    """Serialize payloads deterministically before token accounting."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


@dataclass(frozen=True)
class DeterministicTokenCounter:
    """Provider-free deterministic fallback compatible with the historical estimator."""

    model: str | None = None
    name: str = DETERMINISTIC_TOKENIZER_NAME
    exact: bool = False

    def count(self, payload: Any) -> int:
        serialized = serialize_for_tokens(payload)
        return max(1, math.ceil(len(serialized) / 4))


class TikTokenCounter:
    """Exact local BPE counter backed by the optional ``tiktoken`` package."""

    exact = True

    def __init__(self, *, model: str | None = None, encoding: str | None = None) -> None:
        try:
            import tiktoken
        except ImportError as exc:  # pragma: no cover - exercised without optional extra
            raise TokenizerUnavailableError(
                "tiktoken is not installed; install persistent-memory-mcp[tokenizers]"
            ) from exc

        if model and encoding:
            raise ValueError("Specify either model or encoding, not both")
        if model:
            try:
                resolved = tiktoken.encoding_for_model(model)
            except Exception as exc:
                raise TokenizerUnavailableError(
                    f"tiktoken could not resolve model {model!r}; "
                    "provide an explicit tiktoken:<encoding> identifier or use the deterministic fallback"
                ) from exc
            self.model = model
            self.name = f"tiktoken:{resolved.name}"
            self._encoding = resolved
            return

        encoding_name = encoding or DEFAULT_TIKTOKEN_ENCODING
        try:
            resolved = tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            raise TokenizerUnavailableError(
                f"tiktoken could not load encoding {encoding_name!r}"
            ) from exc
        self.model = None
        self.name = f"tiktoken:{resolved.name}"
        self._encoding = resolved

    def count(self, payload: Any) -> int:
        serialized = serialize_for_tokens(payload)
        return max(1, len(self._encoding.encode(serialized)))


@dataclass(frozen=True)
class TokenMeasurement:
    """Count plus comparison against the deterministic fallback estimator."""

    count: int
    estimated_count: int
    tokenizer: str
    model: str | None
    exact: bool
    fallback: bool
    estimation_error_tokens: int | None
    estimation_error_percent: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "estimated_count": self.estimated_count,
            "tokenizer": self.tokenizer,
            "model": self.model,
            "mode": "exact" if self.exact else "estimated",
            "fallback": self.fallback,
            "estimation_error_tokens": self.estimation_error_tokens,
            "estimation_error_percent": self.estimation_error_percent,
        }


def resolve_token_counter(
    *,
    model: str | None = None,
    tokenizer: str | TokenCounter | None = None,
) -> TokenCounter:
    """Resolve a local token counter, failing closed only for explicit tokenizer requests."""
    if tokenizer is not None and not isinstance(tokenizer, str):
        if not isinstance(tokenizer, TokenCounter):
            raise TypeError("tokenizer must implement the TokenCounter protocol")
        return tokenizer

    requested = (tokenizer or "auto").strip().lower()
    if requested in {"deterministic", "fallback", DETERMINISTIC_TOKENIZER_NAME}:
        return DeterministicTokenCounter(model=model)

    if requested == "auto":
        if model:
            try:
                return TikTokenCounter(model=model)
            except TokenizerUnavailableError:
                pass
        return DeterministicTokenCounter(model=model)

    if requested == "tiktoken":
        return TikTokenCounter(model=model) if model else TikTokenCounter()

    if requested.startswith("tiktoken:"):
        encoding = requested.partition(":")[2].strip()
        if not encoding:
            raise ValueError("tiktoken encoding identifier cannot be empty")
        return TikTokenCounter(encoding=encoding)

    raise ValueError(f"Unknown tokenizer: {tokenizer}")


def measure_tokens(payload: Any, counter: TokenCounter) -> TokenMeasurement:
    """Measure with the active counter and compare against the deterministic fallback."""
    count = counter.count(payload)
    estimate = DeterministicTokenCounter(model=counter.model).count(payload)
    if counter.exact:
        error_tokens = abs(estimate - count)
        error_percent = round((error_tokens / max(1, count)) * 100, 2)
    else:
        error_tokens = None
        error_percent = None
    return TokenMeasurement(
        count=count,
        estimated_count=estimate,
        tokenizer=counter.name,
        model=counter.model,
        exact=counter.exact,
        fallback=not counter.exact,
        estimation_error_tokens=error_tokens,
        estimation_error_percent=error_percent,
    )
