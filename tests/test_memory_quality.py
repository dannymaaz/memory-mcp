from __future__ import annotations

import pytest

from persistent_memory_mcp.memory_quality import detect_memory_relations


def test_detects_near_duplicate_memories() -> None:
    relations = detect_memory_relations(
        [
            {"id": "one", "title": "Restart upload notifier", "content": "Restart only upload notifier on OVH Canada"},
            {"id": "two", "title": "Restart the upload notifier", "content": "Restart only the upload notifier service on OVH Canada"},
        ],
        duplicate_threshold=0.75,
    )
    assert relations
    assert relations[0].relation == "near_duplicate"


def test_detects_conservative_polarity_contradiction() -> None:
    relations = detect_memory_relations(
        [
            {"id": "old", "title": "Enable production uploads", "content": "Allow production uploads for upload notifier"},
            {"id": "new", "title": "Disable production uploads", "content": "Never allow production uploads for upload notifier"},
        ],
        duplicate_threshold=0.95,
        contradiction_threshold=0.35,
    )
    assert any(relation.relation == "possible_contradiction" for relation in relations)


def test_unrelated_memories_are_not_flagged() -> None:
    relations = detect_memory_relations(
        [
            {"id": "auth", "content": "Fix authentication middleware"},
            {"id": "docs", "content": "Update installation documentation"},
        ]
    )
    assert relations == []


def test_threshold_validation() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        detect_memory_relations([], duplicate_threshold=0.5, contradiction_threshold=0.8)
