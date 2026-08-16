"""Reproducible bounds/latency evaluation for SQLite keyset pagination."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from persistent_memory_mcp.storage import SQLiteStorage

RECORDS = 10_000
FOREIGN_RECORDS = 200
PAGE_SIZE = 200
MAX_TOTAL_MS = 5_000.0
MAX_PAGE_MS = 1_000.0
STAMP = "2026-08-16T04:40:00+00:00"


def _seed(storage: SQLiteStorage) -> None:
    storage.insert(
        "projects",
        {
            "id": "project-focus",
            "owner_id": "owner-focus",
            "name": "Pagination benchmark",
            "slug": "pagination-benchmark",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    storage.insert(
        "projects",
        {
            "id": "project-foreign",
            "owner_id": "owner-foreign",
            "name": "Foreign benchmark",
            "slug": "foreign-benchmark",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    focus = [
        (
            f"task-{index:05d}",
            "project-focus",
            "owner-focus",
            f"Task {index}",
            "pending",
            "medium",
            "",
            "internal",
            "{}",
            STAMP,
            STAMP,
        )
        for index in range(RECORDS)
    ]
    foreign = [
        (
            f"foreign-{index:05d}",
            "project-foreign",
            "owner-foreign",
            f"Foreign {index}",
            "pending",
            "medium",
            "",
            "internal",
            "{}",
            STAMP,
            STAMP,
        )
        for index in range(FOREIGN_RECORDS)
    ]
    with storage.connect() as connection:
        connection.executemany(
            "insert into tasks("
            "id, project_id, owner_id, title, status, priority, details, sensitivity, "
            "metadata, created_at, updated_at"
            ") values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [*focus, *foreign],
        )
        connection.commit()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="memory-mcp-pagination-") as directory:
        storage = SQLiteStorage(Path(directory) / "memory.db")
        storage.initialize()
        _seed(storage)
        filters = {"owner_id": "owner-focus", "project_id": "project-focus"}

        cursor: str | None = None
        seen: list[str] = []
        page_times: list[float] = []
        inserted_after_first = False
        started = time.perf_counter()
        while True:
            page_started = time.perf_counter()
            page = storage.select_page(
                "tasks",
                filters,
                limit=PAGE_SIZE,
                cursor=cursor,
            )
            page_times.append((time.perf_counter() - page_started) * 1000)
            seen.extend(str(item["id"]) for item in page.items)

            if not inserted_after_first:
                storage.insert(
                    "tasks",
                    {
                        "id": "task-99999-new",
                        "project_id": "project-focus",
                        "owner_id": "owner-focus",
                        "title": "Inserted after traversal start",
                        "status": "pending",
                        "created_at": STAMP,
                        "updated_at": STAMP,
                    },
                )
                inserted_after_first = True

            if not page.has_more:
                if page.next_cursor is not None:
                    raise RuntimeError("terminal page unexpectedly returned a cursor")
                break
            if not page.next_cursor:
                raise RuntimeError("non-terminal page is missing a cursor")
            cursor = page.next_cursor

        total_ms = (time.perf_counter() - started) * 1000
        fresh = storage.select_page("tasks", filters, limit=PAGE_SIZE)
        checks = {
            "exact_original_record_count": len(seen) == RECORDS,
            "no_duplicates": len(set(seen)) == RECORDS,
            "new_insert_excluded_from_existing_traversal": "task-99999-new" not in seen,
            "new_insert_visible_to_fresh_traversal": any(
                item["id"] == "task-99999-new" for item in fresh.items
            ),
            "owner_project_scope": all(item.startswith("task-") for item in seen),
            "page_count_expected": len(page_times) == RECORDS // PAGE_SIZE,
            "total_latency": total_ms <= MAX_TOTAL_MS,
            "max_page_latency": max(page_times) <= MAX_PAGE_MS,
        }
        result = {
            "fixture": {
                "records": RECORDS,
                "foreign_records": FOREIGN_RECORDS,
                "same_timestamp": True,
                "page_size": PAGE_SIZE,
            },
            "observed": {
                "pages": len(page_times),
                "records_seen": len(seen),
                "total_ms": round(total_ms, 2),
                "max_page_ms": round(max(page_times), 2),
                "mean_page_ms": round(sum(page_times) / len(page_times), 2),
            },
            "thresholds_ms": {
                "total": MAX_TOTAL_MS,
                "page": MAX_PAGE_MS,
            },
            "checks": checks,
            "passed": all(checks.values()),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
