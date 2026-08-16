"""Migration 0002: persist Git-grounded symbol snapshots, changes and evidence links."""

SQL = """
create table if not exists code_symbol_snapshot_runs (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  repository text not null,
  commit_sha text not null,
  ref text not null default '',
  commit_author text not null default '',
  commit_time text,
  symbol_count integer not null default 0,
  files_scanned integer not null default 0,
  files_skipped integer not null default 0,
  captured_at text not null default (datetime('now')),
  metadata text not null default '{}',
  unique(owner_id, project_id, repository, commit_sha)
);

create table if not exists code_symbol_snapshots (
  id text primary key,
  run_id text not null references code_symbol_snapshot_runs(id) on delete cascade,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  repository text not null,
  commit_sha text not null,
  ref text not null default '',
  logical_id text not null,
  source_symbol_id text not null,
  path text not null,
  name text not null,
  qualified_name text not null,
  kind text not null,
  language text not null default '',
  line integer not null,
  end_line integer not null,
  signature text not null default '',
  signature_sha256 text not null,
  body_sha256 text not null,
  file_sha256 text not null,
  first_seen_commit text not null,
  verification_state text not null default 'verified'
    check(verification_state in ('verified','stale','contradicted','missing_source','unverified')),
  created_at text not null default (datetime('now')),
  unique(run_id, source_symbol_id)
);

create table if not exists code_symbol_changes (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  repository text not null,
  from_run_id text references code_symbol_snapshot_runs(id) on delete cascade,
  to_run_id text not null references code_symbol_snapshot_runs(id) on delete cascade,
  from_commit text,
  to_commit text not null,
  logical_id text not null,
  old_snapshot_id text references code_symbol_snapshots(id) on delete set null,
  new_snapshot_id text references code_symbol_snapshots(id) on delete set null,
  change_type text not null
    check(change_type in ('added','modified','moved','renamed','deleted','unchanged')),
  path_changed integer not null default 0,
  name_changed integer not null default 0,
  signature_changed integer not null default 0,
  body_changed integer not null default 0,
  confidence real not null default 1.0,
  created_at text not null default (datetime('now')),
  unique(owner_id, project_id, repository, from_commit, to_commit, logical_id)
);

create table if not exists code_symbol_links (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  repository text not null,
  logical_id text not null,
  snapshot_id text references code_symbol_snapshots(id) on delete set null,
  relation_type text not null,
  target_type text not null
    check(target_type in ('file','commit','test','decision','task','deployment')),
  target_id text not null,
  target_ref text not null default '',
  verification_state text not null default 'verified'
    check(verification_state in ('verified','stale','contradicted','missing_source','unverified')),
  evidence_sha256 text not null default '',
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(owner_id, project_id, repository, logical_id, relation_type, target_type, target_id)
);

create index if not exists idx_symbol_runs_scope
  on code_symbol_snapshot_runs(owner_id, project_id, repository, captured_at desc);
create index if not exists idx_symbol_snapshots_history
  on code_symbol_snapshots(owner_id, project_id, repository, logical_id, created_at desc);
create index if not exists idx_symbol_snapshots_commit
  on code_symbol_snapshots(owner_id, project_id, repository, commit_sha, path);
create index if not exists idx_symbol_changes_history
  on code_symbol_changes(owner_id, project_id, repository, logical_id, created_at desc);
create index if not exists idx_symbol_changes_commit
  on code_symbol_changes(owner_id, project_id, repository, to_commit, change_type);
create index if not exists idx_symbol_links_source
  on code_symbol_links(owner_id, project_id, repository, logical_id, verification_state);
create index if not exists idx_symbol_links_target
  on code_symbol_links(owner_id, project_id, target_type, target_id, verification_state);

PRAGMA user_version = 2;
"""

MIGRATION = {
    "version": 2,
    "name": "symbol_evolution",
    "sql": SQL,
}
