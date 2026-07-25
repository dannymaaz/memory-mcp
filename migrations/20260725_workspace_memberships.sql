-- Workspace membership and role authorization foundation.

create table if not exists workspace_memberships (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id text not null,
  role text not null check (role in ('owner', 'admin', 'member', 'reader')),
  status text not null default 'active' check (status in ('active', 'suspended', 'removed')),
  added_by text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (workspace_id, user_id)
);

create index if not exists idx_workspace_memberships_user
  on workspace_memberships(user_id, status);

create index if not exists idx_workspace_memberships_workspace_role
  on workspace_memberships(workspace_id, role);

alter table workspace_memberships enable row level security;

-- Policy helpers are introduced in the later Supabase Auth integration milestone.
-- Until then, server-side authorization remains the enforcement boundary.
