create or replace function public.enforce_active_groups_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.active and (tg_op = 'INSERT' or not old.active) then
        perform pg_advisory_xact_lock(hashtext(new.user_id::text));

        if (
            select count(*)
            from public.groups
            where user_id = new.user_id
                and active
                and removed_at is null
                and id <> new.id
        ) >= 20 then
            raise exception 'Active groups limit reached' using errcode = 'OF001';
        end if;
    end if;

    return new;
end;
$$;

drop trigger if exists groups_active_limit on public.groups;
create trigger groups_active_limit
    before insert or update of active on public.groups
    for each row execute function public.enforce_active_groups_limit();
