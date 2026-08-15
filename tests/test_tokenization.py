from __future__ import annotations

from pathlib import Path

import pytest

from persistent_memory_mcp.tokenization import (
    DeterministicTokenCounter,
    measure_tokens,
    resolve_token_counter,
)

FIXTURES = Path(__file__).parent / "fixtures"
MAX_REFERENCE_ERROR_PERCENT = 40.0


def test_deterministic_counter_preserves_historical_estimator_contract() -> None:
    counter = DeterministicTokenCounter()
    assert counter.count("abcd") == 1
    assert counter.count("abcdefgh") == 2
    assert counter.count({"mensaje": "hola"}) >= 1


def test_auto_unknown_model_keeps_local_deterministic_fallback() -> None:
    counter = resolve_token_counter(model="provider-model-without-local-mapping", tokenizer="auto")
    assert counter.exact is False
    assert counter.name == "deterministic-char4-v1"
    assert counter.model == "provider-model-without-local-mapping"


def test_unknown_tokenizer_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown tokenizer"):
        resolve_token_counter(tokenizer="remote-magic")


def test_tiktoken_reference_error_is_bounded_for_spanish_and_code() -> None:
    pytest.importorskip("tiktoken")
    reference = resolve_token_counter(model="gpt-4o", tokenizer="tiktoken")

    for fixture_name in ("tokenization_spanish.txt", "tokenization_code.py"):
        payload = (FIXTURES / fixture_name).read_text(encoding="utf-8")
        measurement = measure_tokens(payload, reference)
        assert measurement.exact is True
        assert measurement.estimation_error_percent is not None
        assert measurement.estimation_error_percent <= MAX_REFERENCE_ERROR_PERCENT, (
            fixture_name,
            measurement,
        )
