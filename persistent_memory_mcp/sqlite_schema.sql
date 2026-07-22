pragma foreign_keys = on;

create table if not exists workspaces (
  id text primary key,
  owner_id text not null,
  slug text not null,
  name text not null,
  description text not null default '',
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null,
  unique(owner_id, slug)
);

create table if not exists projects (
  id text primary key,
  owner_id text not null,
  workspace_id text references workspaces(id) on delete set null,
  name text not null,
  slug text not null,
  description text not null default '',
  repo_path text not null default '',
  repo_remote text not null default '',
  repo_status text not null default '{}',
  project_summary text not null default '',
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null,
  unique(owner_id, slug)
);

create table if not exists decisions (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null default 'unknown',
  decision_type text not null default 'general',
  summary text not null,
  details text not null default '',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists tasks (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  title text not null,
  status text not null default 'pending',
  priority text not null default 'medium',
  details text not null default '',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists warnings (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  message text not null,
  severity text not null default 'medium',
  is_active integer not null default 1,
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists sessions (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null,
  model_name text not null default '',
  status text not null default 'active',
  started_at text not null,
  ended_at text,
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists checkpoints (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  title text not null,
  functional_state text not null default '',
  next_steps text not null default '[]',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists file_memory (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  file_path text not null,
  file_role text not null default 'module',
  summary text not null,
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null,
  unique(project_id, file_path)
);

create table if not exists memory_documents (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  source_type text not null,
  source_id text not null,
  title text not null,
  content text not null,
  keywords text not null default '[]',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null,
  unique(project_id, source_type, source_id)
);

create table if not exists timeline_events (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  event_type text not null,
  summary text not null,
  payload text not null default '{}',
  expires_at text,
  created_at text not null,
  updated_at text not null
);

create table if not exists retention_policies (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  keep_recent_sessions integer not null default 5,
  keep_recent_decisions integer not null default 20,
  archive_after_days integer not null default 30,
  metadata text not null default '{}',
  created_at text not null,
  updated_at text not null,
  unique(project_id)
);

create index if not exists idx_projects_owner_slug on projects(owner_id, slug);
create index if not exists idx_decisions_scope on decisions(owner_id, project_id, created_at desc);
create index if not exists idx_tasks_scope on tasks(owner_id, project_id, status);
create index if not exists idx_memory_documents_scope on memory_documents(owner_id, project_id, source_type);
create index if not exists idx_timeline_scope on timeline_events(owner_id, project_id, created_at desc);
