"""Versioned SQLite migrations shipped as normal Python package data."""

from .m0001_v0_3_schema_baseline import MIGRATION as MIGRATION_0001

MIGRATIONS = (MIGRATION_0001,)

__all__ = ["MIGRATIONS", "MIGRATION_0001"]
