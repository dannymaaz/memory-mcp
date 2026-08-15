from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest
from persistent_memory_mcp.migration_service import MigrationChecksumError, MigrationCompatibilityError, MigrationExecutionError, MigrationService
from persistent_memory_mcp.maintenance import verify_backup_manifest
from persistent_memory_mcp.storage import SQLiteStorage

def _db(path:Path):
    s=SQLiteStorage(path); s.initialize()
    with s.connect() as c:
        w=c.execute("insert into workspaces(owner_id,slug,name) values('o','d','D') returning id").fetchone()[0]
        p=c.execute("insert into projects(owner_id,workspace_id,slug,name) values('o',?,'p','P') returning id",(w,)).fetchone()[0]
        c.execute("insert into tasks(project_id,owner_id,title,details) values(?,'o','keep','v0.2')",(p,)); c.commit()

def test_plan_is_read_only(tmp_path:Path):
    db=tmp_path/'m.db'; _db(db); plan=MigrationService(db).plan()
    assert plan.schema_version==0 and plan.pending[0]['version']==1
    with sqlite3.connect(db) as c: assert c.execute("select 1 from sqlite_master where name='schema_migrations'").fetchone() is None

def test_apply_preserves_data_and_creates_verified_backup(tmp_path:Path):
    db=tmp_path/'m.db'; _db(db); result=MigrationService(db).apply(tmp_path/'backups')
    verify_backup_manifest(Path(str(result['backup']['backup_path'])))
    with sqlite3.connect(db) as c:
        assert c.execute('pragma user_version').fetchone()[0]==1
        assert c.execute('select title,details from tasks').fetchone()==('keep','v0.2')
        assert c.execute('select version from schema_migrations').fetchone()==(1,)

def test_idempotent_apply_creates_no_second_backup(tmp_path:Path):
    db=tmp_path/'m.db'; _db(db); service=MigrationService(db); service.apply(tmp_path/'b'); before=list((tmp_path/'b').glob('*.db'))
    assert service.apply(tmp_path/'b')['status']=='current'; assert list((tmp_path/'b').glob('*.db'))==before

def test_checksum_change_rejected(tmp_path:Path):
    db=tmp_path/'m.db'; _db(db); migrations=({"version":1,"name":"x","sql":"PRAGMA user_version=1;"},); s=MigrationService(db,migrations); s.apply(tmp_path/'b')
    with pytest.raises(MigrationChecksumError): MigrationService(db,({"version":1,"name":"x","sql":"PRAGMA user_version=2;"},)).plan()

def test_failed_migration_rolls_back_its_transaction(tmp_path:Path):
    db=tmp_path/'m.db'; _db(db); migrations=({"version":1,"name":"ok","sql":"PRAGMA user_version=1;"},{"version":2,"name":"bad","sql":"create table rollback_me(id integer); insert into missing_table values(1);"})
    with pytest.raises(MigrationExecutionError): MigrationService(db,migrations).apply(tmp_path/'b')
    with sqlite3.connect(db) as c:
        assert c.execute("select 1 from sqlite_master where name='rollback_me'").fetchone() is None
        assert c.execute('select version from schema_migrations order by version').fetchall()==[(1,)]

def test_incompatible_database_rejected_before_backup(tmp_path:Path):
    db=tmp_path/'x.db'; sqlite3.connect(db).execute('create table x(id)').connection.commit()
    with pytest.raises(MigrationCompatibilityError): MigrationService(db).apply(tmp_path/'b')
    assert not (tmp_path/'b').exists()
