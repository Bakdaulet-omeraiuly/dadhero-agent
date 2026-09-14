-- DadHero Story Universe schema.
-- family_id everywhere = auth.uid() of the Supabase-authenticated parent.
-- RLS enforces that a row's owner is the only one who can read/write it --
-- this is the actual multi-tenant boundary; the API layer must never be
-- the only thing enforcing it.

create extension if not exists "pgcrypto";

create table if not exists characters (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  character_name text not null,
  relationship text not null,
  appearance_text text,
  personality_traits text[] not null default '{}',
  role_in_story text not null default '',
  art_style text not null default '',
  reference_image_path text,
  prompt_fragment text not null,
  created_at timestamptz not null default now()
);

create table if not exists places (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  place_name text not null,
  description text not null,
  created_at timestamptz not null default now()
);

create table if not exists stories (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  character_id uuid references characters(id) on delete set null,
  title text not null,
  idea text,
  template_key text not null,
  goal text,
  status text not null default 'draft' check (status in ('draft', 'finished')),
  created_at timestamptz not null default now()
);

create table if not exists pages (
  story_id uuid not null references stories(id) on delete cascade,
  page_number int not null,
  scene_description text not null,
  caption_text text not null,
  image_path text not null,
  is_placeholder boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (story_id, page_number)
);

create table if not exists memories (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  text text not null,
  used_in_story_id uuid references stories(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists progress_updates (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  related_to text not null,
  update_text text not null,
  story_id uuid references stories(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists conversation_messages (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid not null,
  role text not null check (role in ('parent', 'assistant')),
  content text not null,
  tool_calls text[] not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_characters_family on characters(family_id);
create index if not exists idx_places_family on places(family_id);
create index if not exists idx_stories_family on stories(family_id);
create index if not exists idx_memories_family on memories(family_id);
create index if not exists idx_progress_family on progress_updates(family_id);
create index if not exists idx_messages_conversation on conversation_messages(conversation_id, created_at);

alter table characters enable row level security;
alter table places enable row level security;
alter table stories enable row level security;
alter table pages enable row level security;
alter table memories enable row level security;
alter table progress_updates enable row level security;
alter table conversation_messages enable row level security;

create policy "own rows only" on characters for all using (auth.uid() = family_id) with check (auth.uid() = family_id);
create policy "own rows only" on places for all using (auth.uid() = family_id) with check (auth.uid() = family_id);
create policy "own rows only" on stories for all using (auth.uid() = family_id) with check (auth.uid() = family_id);
create policy "own rows only" on memories for all using (auth.uid() = family_id) with check (auth.uid() = family_id);
create policy "own rows only" on progress_updates for all using (auth.uid() = family_id) with check (auth.uid() = family_id);
create policy "own rows only" on conversation_messages for all using (auth.uid() = family_id) with check (auth.uid() = family_id);

-- pages are scoped through their parent story, not a direct family_id column
create policy "own story's pages only" on pages for all
  using (exists (select 1 from stories s where s.id = pages.story_id and s.family_id = auth.uid()))
  with check (exists (select 1 from stories s where s.id = pages.story_id and s.family_id = auth.uid()));
