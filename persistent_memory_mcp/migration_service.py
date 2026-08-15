"""Backup-first, checksum-verified SQLite migrations."""
from __future__ import annotations
import hashlib, sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from .maintenance.backup_service import BackupService
from .sqlite_migrations import MIGRATIONS

_REQUIRED = {"workspaces","projects","decisions","tasks","sessions","warnings"}

class MigrationError(RuntimeError): pass
class MigrationChecksumError(MigrationError): pass
class MigrationCompatibilityError(MigrationError): pass
class MigrationExecutionError(MigrationError): pass

@dataclass(frozen=True)
class MigrationPlan:
    schema_version: int
    pending: tuple[dict[str, object], ...]
    applied: tuple[dict[str, object], ...]
    def as_dict(self): return {"schema_version":self.schema_version,"pending":list(self.pending),"applied":list(self.applied),"backup_required":bool(self.pending)}

class MigrationService:
    def __init__(self, database_path: str | Path, migrations=MIGRATIONS):
        self.database_path=Path(database_path).expanduser().resolve(); self.migrations=tuple(migrations)
    @staticmethod
    def _checksum(sql: str)->str: return hashlib.sha256(sql.encode()).hexdigest()
    def _validate(self):
        if not self.database_path.is_file(): raise MigrationCompatibilityError("SQLite database does not exist")
        with sqlite3.connect(f"file:{self.database_path.as_posix()}?mode=ro",uri=True) as c:
            if str(c.execute("pragma quick_check").fetchone()[0])!="ok": raise MigrationCompatibilityError("SQLite quick_check failed")
            tables={str(r[0]) for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")}
        missing=sorted(_REQUIRED-tables)
        if missing: raise MigrationCompatibilityError("missing required v0.2 tables: "+", ".join(missing))
    def plan(self)->MigrationPlan:
        self._validate()
        with sqlite3.connect(f"file:{self.database_path.as_posix()}?mode=ro",uri=True) as c:
            version=int(c.execute("pragma user_version").fetchone()[0]); exists=c.execute("select 1 from sqlite_master where type='table' and name='schema_migrations'").fetchone()
            rows=c.execute("select version,name,checksum,applied_at from schema_migrations order by version").fetchall() if exists else []
        applied={int(r[0]):r for r in rows}; pending=[]
        for m in self.migrations:
            v=int(m["version"]); ch=self._checksum(str(m["sql"])); name=str(m["name"])
            if v in applied:
                if str(applied[v][2])!=ch: raise MigrationChecksumError(f"applied migration {v:04d}_{name} checksum changed")
            else: pending.append({"version":v,"name":name,"checksum":ch})
        return MigrationPlan(version,tuple(pending),tuple({"version":int(r[0]),"name":str(r[1]),"checksum":str(r[2]),"applied_at":str(r[3])} for r in rows))
    def apply(self, backup_directory: str | Path)->dict[str,object]:
        plan=self.plan()
        if not plan.pending: return {"status":"current","plan":plan.as_dict(),"applied":[],"backup":None}
        stamp=datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"); backup=BackupService(self.database_path).create_backup(Path(backup_directory)/f"pre-migration-{stamp}.db")
        with sqlite3.connect(self.database_path) as c:
            c.execute("create table if not exists schema_migrations (version integer primary key,name text not null,checksum text not null,applied_at text not null)"); c.commit()
        by_version={int(m["version"]):m for m in self.migrations}; done=[]
        for item in plan.pending:
            m=by_version[int(item["version"])]; c=sqlite3.connect(self.database_path)
            try:
                c.executescript("BEGIN IMMEDIATE;\n"+str(m["sql"]))
                c.execute("insert into schema_migrations values (?,?,?,?)",(int(m["version"]),str(m["name"]),self._checksum(str(m["sql"])),datetime.now(UTC).isoformat())); c.commit()
                done.append(item)
            except sqlite3.Error as exc:
                c.rollback(); raise MigrationExecutionError(f"migration {int(m['version']):04d}_{m['name']} failed") from exc
            finally: c.close()
        return {"status":"ok","applied":done,"backup":backup.as_dict(),"plan":self.plan().as_dict()}
