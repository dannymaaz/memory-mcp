"""Migration 0001: establish the first explicit local schema version."""

MIGRATION = {
    "version": 1,
    "name": "v0_3_schema_baseline",
    "sql": "PRAGMA user_version = 1;\n",
}
