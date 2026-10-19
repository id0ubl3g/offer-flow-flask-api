from src.extensions import get_user_supabase, get_supabase_admin

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MIN_SCHEDULE_GAP_MINUTES = 60
MINUTES_PER_DAY = 24 * 60

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

def _utc_minutes(send_time: str, timezone_name: str) -> int:
    hour, minute = (int(part) for part in send_time.split(":")[:2])
    local = datetime.now(ZoneInfo(timezone_name)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    utc = local.astimezone(timezone.utc)

    return utc.hour * 60 + utc.minute

def find_conflicting_schedule(send_time: str, timezone_name: str, exclude_id: str | None = None) -> dict | None:
    target = _utc_minutes(send_time, timezone_name)

    for schedule in list_schedules():
        if schedule["id"] == exclude_id:
            continue

        gap = abs(target - _utc_minutes(schedule["send_time"], schedule["timezone"]))

        if min(gap, MINUTES_PER_DAY - gap) < MIN_SCHEDULE_GAP_MINUTES:
            return serialize_schedule(schedule)

    return None

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