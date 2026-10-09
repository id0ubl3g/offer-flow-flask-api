alter table public.offers add column if not exists tags text[] not null default '{}';
alter table public.groups add column if not exists tags text[] not null default '{}';

alter table public.offers drop constraint if exists offers_tags_limit;
alter table public.offers add constraint offers_tags_limit check (cardinality(tags) <= 10);

alter table public.groups drop constraint if exists groups_tags_limit;
alter table public.groups add constraint groups_tags_limit check (cardinality(tags) <= 10);

create index if not exists offers_tags_idx on public.offers using gin (tags);
