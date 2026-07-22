pragma foreign_keys = on;

create table if not exists workspaces (
  id text primary key default (lower(hex(randomblob(16)))),
  owner_id text not null,
  slug text not null,
  name text not null,
  description text not null default '',
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(owner_id, slug)
);

create table if not exists projects (
  id text primary key default (lower(hex(randomblob(16)))),
  owner_id text not null,
  workspace_id text references workspaces(id) on delete set null,
  name text not null,
  slug text not null,
  description text not null default '',
  primary_interface text not null default 'native',
  repo_path text not null default '',
  repo_remote text not null default '',
  repo_branch text not null default '',
  repo_last_commit text not null default '',
  repo_status text not null default '{}',
  project_summary text not null default '',
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(owner_id, slug)
);

create table if not exists architecture (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  diagram text not null default '',
  summary text not null default '',
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists decisions (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null default 'unknown',
  decision_type text not null default 'general',
  summary text not null,
  details text not null default '',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists tasks (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  title text not null default 'Untitled task',
  status text not null default 'pending',
  priority text not null default 'medium',
  details text not null default '',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists preferences (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  preference_key text not null,
  preference_value text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id, preference_key)
);

create table if not exists sessions (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null,
  model_name text not null default '',
  status text not null default 'active',
  started_at text not null default (datetime('now')),
  ended_at text,
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists warnings (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null default 'unknown',
  message text not null,
  severity text not null default 'medium',
  is_active integer not null default 1,
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists interface_logs (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  interface text not null,
  event_name text not null,
  payload text not null default '{}',
  latency_ms integer not null default 0,
  expires_at text,
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists session_state (
  id text primary key default (lower(hex(randomblob(16)))),
  session_id text not null references sessions(id) on delete cascade,
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  state text not null default '{}',
  metadata text not null default '{}',
  expires_at text,
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(session_id)
);

create table if not exists checkpoints (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  title text not null,
  architecture_summary text not null default '',
  functional_state text not null default '',
  blockers text not null default '[]',
  next_steps text not null default '[]',
  tags text not null default '[]',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists file_memory (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  file_path text not null,
  file_role text not null default 'module',
  summary text not null,
  symbols text not null default '[]',
  importance text not null default 'medium',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id, file_path)
);

create table if not exists file_relations (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  source_file text not null,
  target_file text not null,
  relation_type text not null default 'depends_on',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id, source_file, target_file, relation_type)
);

create table if not exists prompt_patterns (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  title text not null,
  category text not null default 'general',
  prompt text not null,
  usage_notes text not null default '',
  response_style text not null default '',
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id, title)
);

create table if not exists memory_documents (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  source_type text not null,
  source_id text not null,
  title text not null,
  content text not null,
  keywords text not null default '[]',
  embedding text,
  sensitivity text not null default 'internal',
  expires_at text,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id, source_type, source_id)
);

create table if not exists timeline_events (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  event_type text not null,
  summary text not null,
  payload text not null default '{}',
  expires_at text,
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);

create table if not exists retention_policies (
  id text primary key default (lower(hex(randomblob(16)))),
  project_id text not null references projects(id) on delete cascade,
  owner_id text not null,
  keep_recent_sessions integer not null default 5,
  keep_recent_decisions integer not null default 20,
  archive_after_days integer not null default 30,
  summarize_archived integer not null default 1,
  metadata text not null default '{}',
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  unique(project_id)
);

create index if not exists idx_projects_owner_slug on projects(owner_id, slug);
create index if not exists idx_decisions_scope on decisions(owner_id, project_id, created_at desc);
create index if not exists idx_tasks_scope on tasks(owner_id, project_id, status);
create index if not exists idx_sessions_scope on sessions(owner_id, project_id, status);
create index if not exists idx_warnings_scope on warnings(owner_id, project_id, is_active);
create index if not exists idx_memory_documents_scope on memory_documents(owner_id, project_id, source_type);
create index if not exists idx_timeline_scope on timeline_events(owner_id, project_id, created_at desc);
