create table if not exists public.whatsapp_instances (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users (id) on delete cascade,
    instance_name text not null unique,
    instance_token text not null,
    status text not null default 'connecting' check (status in ('connecting', 'open', 'close')),
    phone text,
    profile_name text,
    connected_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists whatsapp_instances_set_updated_at on public.whatsapp_instances;
create trigger whatsapp_instances_set_updated_at
    before update on public.whatsapp_instances
    for each row execute function public.set_updated_at();

alter table public.whatsapp_instances enable row level security;

create table if not exists public.groups (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    instance_id uuid not null references public.whatsapp_instances (id) on delete cascade,
    jid text not null check (jid like '%@g.us'),
    name text not null,
    participants_count integer,
    is_announce boolean not null default false,
    is_admin boolean,
    can_send boolean generated always as (not is_announce or coalesce(is_admin, false)) stored,
    active boolean not null default false,
    removed_at timestamptz,
    synced_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint groups_instance_jid_key unique (instance_id, jid)
);

create index if not exists groups_user_id_active_idx on public.groups (user_id, active);

drop trigger if exists groups_set_updated_at on public.groups;
create trigger groups_set_updated_at
    before update on public.groups
    for each row execute function public.set_updated_at();

alter table public.groups enable row level security;

drop policy if exists "groups_select_own" on public.groups;
create policy "groups_select_own" on public.groups
    for select to authenticated
    using ((select auth.uid()) = user_id);