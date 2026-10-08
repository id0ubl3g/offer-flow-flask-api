create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    name text not null,
    email text not null,
    created_at timestamptz not null default now(),
    constraint profiles_email_key unique (email)
);