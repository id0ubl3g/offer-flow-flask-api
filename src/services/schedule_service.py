from src.extensions import get_user_supabase, get_supabase_admin

DEFAULT_SETTINGS = {
    "min_delay_seconds": 8,
    "max_delay_seconds": 25,
    "daily_limit": 200
}

def serialize_schedule(schedule: dict) -> dict:
    return {
        **schedule,
        "send_time": schedule["send_time"][:5]
    }

def list_schedules() -> list[dict]:
    response = (
        get_user_supabase()
        .table("schedules")
        .select("*")
        .order("send_time")
        .execute()
    )

    return response.data

def get_schedule(schedule_id: str) -> dict | None:
    response = (
        get_user_supabase()
        .table("schedules")
        .select("*")
        .eq("id", schedule_id)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def find_schedule_by_time(send_time: str) -> dict | None:
    response = (
        get_user_supabase()
        .table("schedules")
        .select("id")
        .eq("send_time", send_time)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def create_schedule(user_id: str, data: dict) -> dict:
    response = (
        get_user_supabase()
        .table("schedules")
        .insert({**data, "user_id": user_id})
        .execute()
    )

    return response.data[0]

def update_schedule(schedule_id: str, data: dict) -> dict | None:
    response = (
        get_user_supabase()
        .table("schedules")
        .update(data)
        .eq("id", schedule_id)
        .execute()
    )

    return response.data[0] if response.data else None

def delete_schedule(schedule_id: str) -> None:
    get_user_supabase().table("schedules").delete().eq("id", schedule_id).execute()

def get_settings(user_id: str, admin: bool = False) -> dict:
    client = get_supabase_admin() if admin else get_user_supabase()

    response = (
        client
        .table("dispatch_settings")
        .select("min_delay_seconds, max_delay_seconds, daily_limit")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    return {**DEFAULT_SETTINGS, **(response.data if response and response.data else {})}

def save_settings(user_id: str, data: dict) -> dict:
    response = (
        get_user_supabase()
        .table("dispatch_settings")
        .upsert({**data, "user_id": user_id}, on_conflict="user_id")
        .execute()
    )

    row = response.data[0]

    return {key: row[key] for key in DEFAULT_SETTINGS}