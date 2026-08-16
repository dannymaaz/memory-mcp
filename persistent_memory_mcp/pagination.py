"""Deterministic opaque keyset pagination primitives."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

CURSOR_VERSION = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class PaginationError(ValueError):
    """Base error for invalid pagination requests."""


class InvalidCursorError(PaginationError):
    """Raised when a cursor is malformed or does not match the current query."""


@dataclass(frozen=True)
class CursorBoundary:
    order_value: str
    record_id: str
    anchor_rowid: int


@dataclass(frozen=True)
class StoragePage:
    """Bounded storage page returned by a deterministic keyset query."""

    items: list[dict[str, Any]]
    next_cursor: str | None
    has_more: bool
    limit: int
    order_by: str
    descending: bool
    cursor_version: int = CURSOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "limit": self.limit,
            "order_by": self.order_by,
            "descending": self.descending,
            "cursor_version": self.cursor_version,
        }


def normalize_page_size(value: int | None) -> int:
    if value is None:
        return DEFAULT_PAGE_SIZE
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise PaginationError("page size must be an integer") from exc
    if resolved < 1 or resolved > MAX_PAGE_SIZE:
        raise PaginationError(f"page size must be between 1 and {MAX_PAGE_SIZE}")
    return resolved


def query_fingerprint(
    *,
    table: str,
    filters: Mapping[str, Any] | None,
    order_by: str,
    descending: bool,
) -> str:
    """Hash query identity without embedding filter values in the cursor."""
    payload = {
        "v": CURSOR_VERSION,
        "table": table,
        "filters": dict(sorted((filters or {}).items())),
        "order_by": order_by,
        "descending": bool(descending),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def encode_cursor(*, fingerprint: str, boundary: CursorBoundary) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "q": fingerprint,
        "o": boundary.order_value,
        "i": boundary.record_id,
        "a": int(boundary.anchor_rowid),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, *, expected_fingerprint: str) -> CursorBoundary:
    if not isinstance(cursor, str) or not cursor.strip():
        raise InvalidCursorError("cursor must be a non-empty string")
    token = cursor.strip()
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc
    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        raise InvalidCursorError("cursor version is unsupported")
    if payload.get("q") != expected_fingerprint:
        raise InvalidCursorError("cursor does not match the current query")
    order_value = payload.get("o")
    record_id = payload.get("i")
    anchor = payload.get("a")
    if not isinstance(order_value, str) or not isinstance(record_id, str):
        raise InvalidCursorError("cursor boundary is invalid")
    if not isinstance(anchor, int) or anchor < 0:
        raise InvalidCursorError("cursor anchor is invalid")
    return CursorBoundary(order_value=order_value, record_id=record_id, anchor_rowid=anchor)
