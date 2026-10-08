alter table public.profiles enable row level security;

do $$
declare
    policy record;
begin
    for policy in
        select policyname from pg_policies where schemaname = 'public' and tablename = 'profiles'
    loop
        execute format('drop policy %I on public.profiles', policy.policyname);
    end loop;
end
$$;

create policy "profiles_select_own" on public.profiles
    for select to authenticated
    using ((select auth.uid()) = id);

create policy "profiles_update_own" on public.profiles
    for update to authenticated
    using ((select auth.uid()) = id)
    with check ((select auth.uid()) = id);