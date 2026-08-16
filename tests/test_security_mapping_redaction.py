from __future__ import annotations

from persistent_memory_mcp.security import redact_sensitive_value


def test_sensitive_mapping_keys_are_redacted_even_for_short_non_provider_values() -> None:
    result = redact_sensitive_value(
        {
            "token": "secret-value",
            "password": "short",
            "nested": {"access-token": "abc", "safe": "visible"},
            "token_count": 123,
        }
    )
    assert result.value["token"] == "[REDACTED:sensitive_field]"
    assert result.value["password"] == "[REDACTED:sensitive_field]"
    assert result.value["nested"]["access-token"] == "[REDACTED:sensitive_field]"
    assert result.value["nested"]["safe"] == "visible"
    assert result.value["token_count"] == 123
    assert result.redactions.count("sensitive_field") == 3


def test_empty_sensitive_fields_preserve_empty_shape_without_false_redaction() -> None:
    result = redact_sensitive_value({"token": "", "secret": None})
    assert result.value == {"token": "", "secret": None}
    assert result.redactions == ()
