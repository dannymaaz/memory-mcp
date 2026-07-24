create table if not exists deployment_records (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  owner_id text not null,
  service text not null,
  environment text not null,
  host text not null,
  directory text not null,
  restart_command text not null,
  commit_sha text not null,
  result text not null,
  operator text,
  tests jsonb not null default '[]'::jsonb,
  rollback_target text,
  rollback_plan jsonb not null default '{}'::jsonb,
  risk_level text not null default 'low',
  risk_reasons jsonb not null default '[]'::jsonb,
  confirmation_recorded boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_deployment_records_scope
  on deployment_records(owner_id, project_id, service, environment, created_at desc);
