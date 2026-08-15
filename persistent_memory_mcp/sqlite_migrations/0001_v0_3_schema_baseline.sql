-- Persistent Memory MCP v0.3 local schema baseline.
-- The v0.2 schema already contains the current tables and indexes; this migration
-- establishes an explicit local schema version for reproducible future upgrades.
PRAGMA user_version = 1;
