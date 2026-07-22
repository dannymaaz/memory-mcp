-- Security, provenance and retention metadata for Persistent Memory MCP.

alter table decisions add column if not exists expires_at timestamptz;
alter table tasks add column if not exists expires_at timestamptz;
alter table warnings add column if not exists expires_at timestamptz;
alter table sessions add column if not exists expires_at timestamptz;
alter table session_state add column if not exists expires_at timestamptz;
alter table checkpoints add column if not exists expires_at timestamptz;
alter table file_memory add column if not exists expires_at timestamptz;
alter table file_relations add column if not exists expires_at timestamptz;
alter table prompt_patterns add column if not exists expires_at timestamptz;
alter table memory_documents add column if not exists expires_at timestamptz;
alter table timeline_events add column if not exists expires_at timestamptz;
alter table interface_logs add column if not exists expires_at timestamptz;

alter table decisions add column if not exists sensitivity text not null default 'internal';
alter table tasks add column if not exists sensitivity text not null default 'internal';
alter table warnings add column if not exists sensitivity text not null default 'internal';
alter table checkpoints add column if not exists sensitivity text not null default 'internal';
alter table file_memory add column if not exists sensitivity text not null default 'internal';
alter table prompt_patterns add column if not exists sensitivity text not null default 'internal';
alter table memory_documents add column if not exists sensitivity text not null default 'internal';

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'decisions', 'tasks', 'warnings', 'checkpoints',
    'file_memory', 'prompt_patterns', 'memory_documents'
  ]
  loop
    if not exists (
      select 1
      from pg_constraint
      where conname = table_name || '_sensitivity_check'
    ) then
      execute format(
        'alter table %I add constraint %I check (sensitivity in (''public'', ''internal'', ''confidential'', ''restricted'')) not valid',
        table_name,
        table_name || '_sensitivity_check'
      );
    end if;
  end loop;
end
$$;

create index if not exists idx_decisions_owner_project_expiry
  on decisions(owner_id, project_id, expires_at);
create index if not exists idx_tasks_owner_project_expiry
  on tasks(owner_id, project_id, expires_at);
create index if not exists idx_warnings_owner_project_expiry
  on warnings(owner_id, project_id, expires_at);
create index if not exists idx_sessions_owner_project_expiry
  on sessions(owner_id, project_id, expires_at);
create index if not exists idx_checkpoints_owner_project_expiry
  on checkpoints(owner_id, project_id, expires_at);
create index if not exists idx_file_memory_owner_project_expiry
  on file_memory(owner_id, project_id, expires_at);
create index if not exists idx_memory_documents_owner_project_expiry
  on memory_documents(owner_id, project_id, expires_at);

-- Destructive operations must always include owner_id and project_id in their filters.
-- Service-layer dry-run planning is required before deletion execution.
