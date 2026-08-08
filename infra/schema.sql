-- AI Knowledge Graph Builder - Supabase Schema
-- Run this in Supabase SQL Editor to set up the database schema with RLS.

-- profiles mirrors auth.users, extends with app-specific fields
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  created_at timestamptz default now()
);

create table projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  owner_id uuid references profiles(id) on delete set null,
  created_at timestamptz default now()
);

create table project_members (
  project_id uuid references projects(id) on delete cascade,
  user_id uuid references profiles(id) on delete cascade,
  role text check (role in ('owner','editor','viewer')) default 'viewer',
  primary key (project_id, user_id)
);

create table documents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  uploaded_by uuid references profiles(id) on delete set null,
  filename text not null,
  file_type text not null,
  storage_path text not null,
  status text check (status in ('pending','processing','processed','failed')) default 'pending',
  page_count int,
  error_message text,
  uploaded_at timestamptz default now(),
  processed_at timestamptz
);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  chunk_index int not null,
  page_number int,
  section_index int default 0,
  text text not null,
  token_count int,
  chroma_id text not null
);

create table entities (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  name text not null,
  type text check (type in ('person','organization','concept','location','date','other')),
  description text,
  first_seen_document_id uuid references documents(id) on delete set null,
  created_at timestamptz default now(),
  unique (project_id, name, type)
);

create table entity_mentions (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid references entities(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  chunk_id uuid references document_chunks(id) on delete set null,
  mention_text text,
  confidence float
);

create table relationships (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  source_entity_id uuid references entities(id) on delete cascade,
  target_entity_id uuid references entities(id) on delete cascade,
  relation_type text not null,
  description text,
  confidence float,
  source_document_id uuid references documents(id) on delete set null,
  created_at timestamptz default now()
);

create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  user_id uuid references profiles(id) on delete set null,
  title text,
  created_at timestamptz default now()
);

create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references chat_sessions(id) on delete cascade,
  role text check (role in ('user','assistant')) not null,
  content text not null,
  citations jsonb,
  created_at timestamptz default now()
);

create table agents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  name text not null,
  type text not null,
  config jsonb default '{}',
  status text default 'active',
  created_at timestamptz default now()
);

create table agent_tasks (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  input jsonb,
  output jsonb,
  status text check (status in ('queued','running','completed','failed')) default 'queued',
  trace jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  error text
);

create table mcp_connections (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  direction text check (direction in ('sender','receiver')),
  name text not null,
  endpoint_url text,
  auth_config jsonb,
  status text default 'disconnected'
);

create table agent_skills (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  skill_type text not null,
  content text not null,
  evidence text,
  success_count int default 0,
  failure_count int default 0,
  helpful_count int default 0,
  harmful_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table agent_run_traces (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  task_id uuid references agent_tasks(id) on delete set null,
  input_text text not null,
  output_text text,
  tool_calls jsonb,
  scores jsonb,
  skills_used uuid[],
  created_at timestamptz default now()
);

create table refinement_eval_sets (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  split text not null check (split in ('held_in','held_out')),
  task_name text not null,
  input_text text not null,
  expected_output jsonb,
  created_at timestamptz default now()
);

create table refinement_logs (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  task_id uuid references agent_tasks(id) on delete set null,
  action text not null,
  target_id uuid,
  reason text not null,
  before jsonb,
  after jsonb,
  held_in_delta float,
  held_out_delta float,
  accepted boolean default false,
  created_at timestamptz default now()
);

create table webhook_subscriptions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  event_type text not null,
  url text not null,
  secret text,
  active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  subscription_id uuid references webhook_subscriptions(id) on delete cascade,
  event_type text not null,
  payload jsonb not null,
  response_status int,
  response_body text,
  attempts int default 0,
  success boolean default false,
  next_retry_at timestamptz,
  created_at timestamptz default now()
);

create table inbound_webhooks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  name text not null,
  slug text not null unique,
  handler text not null,
  config jsonb default '{}',
  active boolean default true,
  created_at timestamptz default now()
);

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  actor_id uuid references profiles(id) on delete set null,
  action text not null,
  resource_type text,
  resource_id uuid,
  metadata jsonb,
  created_at timestamptz default now()
);

-- Row Level Security
alter table profiles enable row level security;
alter table projects enable row level security;
alter table project_members enable row level security;
alter table documents enable row level security;
alter table document_chunks enable row level security;
alter table entities enable row level security;
alter table entity_mentions enable row level security;
alter table relationships enable row level security;
alter table chat_sessions enable row level security;
alter table chat_messages enable row level security;
alter table agents enable row level security;
alter table agent_tasks enable row level security;
alter table mcp_connections enable row level security;
alter table agent_skills enable row level security;
alter table agent_run_traces enable row level security;
alter table refinement_eval_sets enable row level security;
alter table refinement_logs enable row level security;
alter table webhook_subscriptions enable row level security;
alter table webhook_deliveries enable row level security;
alter table inbound_webhooks enable row level security;
alter table audit_log enable row level security;

-- RLS policies: users can only access projects they are members of
create policy "Users can view own profile" on profiles
  for select using (auth.uid() = id);

create policy "Users can update own profile" on profiles
  for update using (auth.uid() = id);

create policy "Members can view project" on projects
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = projects.id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view project members" on project_members
  for select using (
    exists (
      select 1 from project_members pm
      where pm.project_id = project_members.project_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view documents" on documents
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = documents.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can insert documents" on documents
  for insert with check (
    exists (
      select 1 from project_members
      where project_members.project_id = documents.project_id
      and project_members.user_id = auth.uid()
      and project_members.role in ('owner', 'editor')
    )
  );

create policy "Members can view chunks" on document_chunks
  for select using (
    exists (
      select 1 from documents d
      join project_members pm on pm.project_id = d.project_id
      where d.id = document_chunks.document_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view entities" on entities
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = entities.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view entity_mentions" on entity_mentions
  for select using (
    exists (
      select 1 from entities e
      join project_members pm on pm.project_id = e.project_id
      where e.id = entity_mentions.entity_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view relationships" on relationships
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = relationships.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view chat sessions" on chat_sessions
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = chat_sessions.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view chat messages" on chat_messages
  for select using (
    exists (
      select 1 from chat_sessions cs
      join project_members pm on pm.project_id = cs.project_id
      where cs.id = chat_messages.session_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view agents" on agents
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = agents.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view agent tasks" on agent_tasks
  for select using (
    exists (
      select 1 from agents a
      join project_members pm on pm.project_id = a.project_id
      where a.id = agent_tasks.agent_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view mcp connections" on mcp_connections
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = mcp_connections.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view agent skills" on agent_skills
  for select using (
    exists (
      select 1 from agents a
      join project_members pm on pm.project_id = a.project_id
      where a.id = agent_skills.agent_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view agent run traces" on agent_run_traces
  for select using (
    exists (
      select 1 from agents a
      join project_members pm on pm.project_id = a.project_id
      where a.id = agent_run_traces.agent_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view refinement eval sets" on refinement_eval_sets
  for select using (
    exists (
      select 1 from agents a
      join project_members pm on pm.project_id = a.project_id
      where a.id = refinement_eval_sets.agent_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view refinement logs" on refinement_logs
  for select using (
    exists (
      select 1 from agents a
      join project_members pm on pm.project_id = a.project_id
      where a.id = refinement_logs.agent_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view webhook subscriptions" on webhook_subscriptions
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = webhook_subscriptions.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view webhook deliveries" on webhook_deliveries
  for select using (
    exists (
      select 1 from webhook_subscriptions ws
      join project_members pm on pm.project_id = ws.project_id
      where ws.id = webhook_deliveries.subscription_id
      and pm.user_id = auth.uid()
    )
  );

create policy "Members can view inbound webhooks" on inbound_webhooks
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = inbound_webhooks.project_id
      and project_members.user_id = auth.uid()
    )
  );

create policy "Members can view audit log" on audit_log
  for select using (
    exists (
      select 1 from project_members
      where project_members.project_id = audit_log.project_id
      and project_members.user_id = auth.uid()
    )
  );

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$ language plpgsql security definer;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
