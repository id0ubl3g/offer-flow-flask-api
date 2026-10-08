create table if not exists public.offers (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    product_name text not null check (char_length(product_name) between 2 and 200),
    url text not null check (url ~* '^https?://' and char_length(url) <= 2048),
    message text check (char_length(message) <= 4000),
    original_price_cents integer not null check (original_price_cents > 0),
    price_cents integer not null check (price_cents > 0),
    discount_percent smallint generated always as (
        round(100.0 * (original_price_cents - price_cents) / original_price_cents)::smallint
    ) stored,
    image_path text,
    status text not null default 'draft' check (status in ('draft', 'queued', 'sent', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint offers_price_not_above_original check (price_cents <= original_price_cents)
);

create index if not exists offers_user_id_created_at_idx on public.offers (user_id, created_at desc);
create index if not exists offers_user_id_status_idx on public.offers (user_id, status);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists offers_set_updated_at on public.offers;
create trigger offers_set_updated_at
    before update on public.offers
    for each row execute function public.set_updated_at();

alter table public.offers enable row level security;

drop policy if exists "offers_select_own" on public.offers;
create policy "offers_select_own" on public.offers
    for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "offers_insert_own" on public.offers;
create policy "offers_insert_own" on public.offers
    for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "offers_update_own" on public.offers;
create policy "offers_update_own" on public.offers
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "offers_delete_own" on public.offers;
create policy "offers_delete_own" on public.offers
    for delete to authenticated
    using ((select auth.uid()) = user_id);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('offer-images', 'offer-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "offer_images_insert_own" on storage.objects;
create policy "offer_images_insert_own" on storage.objects
    for insert to authenticated
    with check (bucket_id = 'offer-images' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "offer_images_select_own" on storage.objects;
create policy "offer_images_select_own" on storage.objects
    for select to authenticated
    using (bucket_id = 'offer-images' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "offer_images_delete_own" on storage.objects;
create policy "offer_images_delete_own" on storage.objects
    for delete to authenticated
    using (bucket_id = 'offer-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
