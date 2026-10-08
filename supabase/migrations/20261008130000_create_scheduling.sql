alter table public.offers add column if not exists queued_at timestamptz;

create index if not exists offers_queue_idx on public.offers (user_id, queued_at) where status = 'queued';

create table if not exists public.schedules (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    send_time time not null,
    days_of_week smallint[] not null default array[1, 2, 3, 4, 5, 6, 7]::smallint[],
    timezone text not null default 'America/Sao_Paulo',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint schedules_days_valid check (
        cardinality(days_of_week) between 1 and 7
        and days_of_week <@ array[1, 2, 3, 4, 5, 6, 7]::smallint[]
    ),
    constraint schedules_user_time_key unique (user_id, send_time)
);

create index if not exists schedules_active_idx on public.schedules (active);

drop trigger if exists schedules_set_updated_at on public.schedules;
create trigger schedules_set_updated_at
    before update on public.schedules
    for each row execute function public.set_updated_at();

alter table public.schedules enable row level security;

drop policy if exists "schedules_select_own" on public.schedules;
create policy "schedules_select_own" on public.schedules
    for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "schedules_insert_own" on public.schedules;
create policy "schedules_insert_own" on public.schedules
    for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "schedules_update_own" on public.schedules;
create policy "schedules_update_own" on public.schedules
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "schedules_delete_own" on public.schedules;
create policy "schedules_delete_own" on public.schedules
    for delete to authenticated
    using ((select auth.uid()) = user_id);

create table if not exists public.dispatch_settings (
    user_id uuid primary key references auth.users (id) on delete cascade,
    min_delay_seconds integer not null default 8 check (min_delay_seconds >= 5),
    max_delay_seconds integer not null default 25 check (max_delay_seconds <= 300),
    daily_limit integer not null default 200 check (daily_limit between 1 and 1000),
    updated_at timestamptz not null default now(),
    constraint dispatch_settings_delay_range check (min_delay_seconds <= max_delay_seconds)
);

drop trigger if exists dispatch_settings_set_updated_at on public.dispatch_settings;
create trigger dispatch_settings_set_updated_at
    before update on public.dispatch_settings
    for each row execute function public.set_updated_at();

alter table public.dispatch_settings enable row level security;

drop policy if exists "dispatch_settings_select_own" on public.dispatch_settings;
create policy "dispatch_settings_select_own" on public.dispatch_settings
    for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "dispatch_settings_insert_own" on public.dispatch_settings;
create policy "dispatch_settings_insert_own" on public.dispatch_settings
    for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "dispatch_settings_update_own" on public.dispatch_settings;
create policy "dispatch_settings_update_own" on public.dispatch_settings
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create table if not exists public.dispatch_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    schedule_id uuid references public.schedules (id) on delete set null,
    offer_id uuid references public.offers (id) on delete set null,
    offer_name text,
    scheduled_for timestamptz not null,
    status text not null default 'running' check (status in ('running', 'completed', 'failed', 'skipped')),
    error text,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    constraint dispatch_runs_schedule_slot_key unique (schedule_id, scheduled_for)
);

create index if not exists dispatch_runs_user_idx on public.dispatch_runs (user_id, scheduled_for desc);
create index if not exists dispatch_runs_running_idx on public.dispatch_runs (status) where status = 'running';

alter table public.dispatch_runs enable row level security;

drop policy if exists "dispatch_runs_select_own" on public.dispatch_runs;
create policy "dispatch_runs_select_own" on public.dispatch_runs
    for select to authenticated
    using ((select auth.uid()) = user_id);

create table if not exists public.dispatches (
    id uuid primary key default gen_random_uuid(),
    run_id uuid references public.dispatch_runs (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    offer_id uuid references public.offers (id) on delete set null,
    group_id uuid references public.groups (id) on delete set null,
    group_name text not null,
    status text not null default 'pending' check (status in ('pending', 'sent', 'failed', 'skipped')),
    attempts integer not null default 0,
    error text,
    sent_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists dispatches_run_idx on public.dispatches (run_id);
create index if not exists dispatches_user_status_idx on public.dispatches (user_id, status, created_at desc);
create index if not exists dispatches_user_sent_at_idx on public.dispatches (user_id, sent_at) where status = 'sent';

alter table public.dispatches enable row level security;

drop policy if exists "dispatches_select_own" on public.dispatches;
create policy "dispatches_select_own" on public.dispatches
    for select to authenticated
    using ((select auth.uid()) = user_id);