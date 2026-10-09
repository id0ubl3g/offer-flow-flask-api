from src.extensions import get_supabase_admin, get_user_supabase
from src.services import offer_service, schedule_service, whatsapp_service
from src.services.evolution_client import EvolutionError

from datetime import datetime, timedelta, timezone
from postgrest.exceptions import APIError
from zoneinfo import ZoneInfo
from typing import Callable
import logging
import random
import time

CATCH_UP_WINDOW = timedelta(minutes=10)
SEND_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 5

logger = logging.getLogger(__name__)

def _now() -> datetime:
    return datetime.now(timezone.utc)

def due_slot(schedule: dict, now: datetime) -> datetime | None:
    local_now = now.astimezone(ZoneInfo(schedule["timezone"]))
    hour, minute = (int(part) for part in schedule["send_time"].split(":")[:2])

    slot = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if slot > local_now:
        slot -= timedelta(days=1)

    if local_now - slot > CATCH_UP_WINDOW or slot.isoweekday() not in schedule["days_of_week"]:
        return None

    return slot.astimezone(timezone.utc)

def list_active_schedules() -> list[dict]:
    return get_supabase_admin().table("schedules").select("*").eq("active", True).execute().data

def create_run(schedule: dict, scheduled_for: datetime) -> dict | None:
    try:
        response = (
            get_supabase_admin()
            .table("dispatch_runs")
            .insert({
                "user_id": schedule["user_id"],
                "schedule_id": schedule["id"],
                "scheduled_for": scheduled_for.isoformat()
            })
            .execute()
        )

    except APIError as e:
        if e.code == "23505":
            return None

        raise

    return response.data[0]

def recover_interrupted_runs(active_run_ids: set[str]) -> int:
    admin = get_supabase_admin()
    running = admin.table("dispatch_runs").select("id").eq("status", "running").execute().data
    interrupted = [run["id"] for run in running if run["id"] not in active_run_ids]

    for run_id in interrupted:
        fail_run(run_id, "Worker interrupted")

    return len(interrupted)

def fail_run(run_id: str, error: str) -> None:
    get_supabase_admin().table("dispatches").update({"status": "failed", "error": error}).eq("run_id", run_id).eq("status", "pending").execute()
    _finish_run(run_id, "failed", error)

def _finish_run(run_id: str, status: str, error: str | None = None) -> None:
    get_supabase_admin().table("dispatch_runs").update({
        "status": status,
        "error": error,
        "finished_at": _now().isoformat()
    }).eq("id", run_id).execute()

def _update_dispatch(dispatch_id: str, data: dict) -> None:
    get_supabase_admin().table("dispatches").update(data).eq("id", dispatch_id).execute()

def sent_today(user_id: str, timezone_name: str) -> int:
    local_midnight = _now().astimezone(ZoneInfo(timezone_name)).replace(hour=0, minute=0, second=0, microsecond=0)

    response = (
        get_supabase_admin()
        .table("dispatches")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("status", "sent")
        .gte("sent_at", local_midnight.astimezone(timezone.utc).isoformat())
        .limit(1)
        .execute()
    )

    return response.count or 0

def _queued_offers(user_id: str) -> list[dict]:
    return (
        get_supabase_admin()
        .table("offers")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "queued")
        .order("queued_at")
        .execute()
        .data
    )

def groups_for_offer(offer: dict, groups: list[dict]) -> list[dict]:
    offer_tags = set(offer.get("tags") or [])

    return [group for group in groups if not group.get("tags") or offer_tags & set(group["tags"])]

def _next_offer_with_groups(user_id: str, groups: list[dict]) -> tuple[dict | None, list[dict]]:
    for offer in _queued_offers(user_id):
        matched = groups_for_offer(offer, groups)

        if matched:
            return offer, matched

    return None, []

def _active_groups(user_id: str) -> list[dict]:
    return (
        get_supabase_admin()
        .table("groups")
        .select("*")
        .eq("user_id", user_id)
        .eq("active", True)
        .eq("can_send", True)
        .is_("removed_at", "null")
        .order("name")
        .execute()
        .data
    )

def _send_with_retry(instance: dict, group: dict, message: str, image_url: str | None, wait: Callable[[float], bool]) -> tuple[bool, int, str | None]:
    error = None

    for attempt in range(1, SEND_ATTEMPTS + 1):
        try:
            whatsapp_service.send_offer(instance, group, message, image_url)
            return True, attempt, None

        except EvolutionError as e:
            error = e.message

            if attempt < SEND_ATTEMPTS and wait(RETRY_DELAY_SECONDS):
                break

    return False, SEND_ATTEMPTS, error

def _is_connected(instance: dict) -> bool:
    try:
        return whatsapp_service.refresh_status(instance)["status"] == "open"

    except EvolutionError:
        return False

def process_run(run: dict, schedule: dict, wait: Callable[[float], bool]) -> str:
    user_id = run["user_id"]
    admin = get_supabase_admin()

    instance = whatsapp_service.get_instance(user_id)

    if instance is None or not _is_connected(instance):
        _finish_run(run["id"], "failed", "WhatsApp is not connected")
        return "failed"

    settings = schedule_service.get_settings(user_id, admin=True)
    remaining = settings["daily_limit"] - sent_today(user_id, schedule["timezone"])

    if remaining <= 0:
        _finish_run(run["id"], "skipped", "Daily limit reached")
        return "skipped"

    groups = _active_groups(user_id)

    if not groups:
        _finish_run(run["id"], "skipped", "No active groups")
        return "skipped"

    offer, groups = _next_offer_with_groups(user_id, groups)

    if offer is None:
        _finish_run(run["id"], "skipped", "No queued offer matches the active groups")
        return "skipped"

    admin.table("dispatch_runs").update({"offer_id": offer["id"], "offer_name": offer["product_name"]}).eq("id", run["id"]).execute()

    dispatches = admin.table("dispatches").insert([
        {
            "run_id": run["id"],
            "user_id": user_id,
            "offer_id": offer["id"],
            "group_id": group["id"],
            "group_name": group["name"]
        }
        for group in groups
    ]).execute().data

    groups_by_id = {group["id"]: group for group in groups}
    message = offer_service.render_message(offer)
    image_url = offer_service.get_image_url(offer.get("image_path"))

    sent = 0
    stop_reason = None

    for index, dispatch in enumerate(dispatches):
        if stop_reason is None and sent >= remaining:
            stop_reason = ("skipped", "Daily limit reached")

        if stop_reason is None and index > 0 and wait(random.uniform(settings["min_delay_seconds"], settings["max_delay_seconds"])):
            stop_reason = ("skipped", "Worker stopped")

        if stop_reason:
            _update_dispatch(dispatch["id"], {"status": stop_reason[0], "error": stop_reason[1]})
            continue

        success, attempts, error = _send_with_retry(instance, groups_by_id[dispatch["group_id"]], message, image_url, wait)

        if success:
            sent += 1
            _update_dispatch(dispatch["id"], {"status": "sent", "attempts": attempts, "sent_at": _now().isoformat()})
            continue

        _update_dispatch(dispatch["id"], {"status": "failed", "attempts": attempts, "error": error})

        if not _is_connected(instance):
            stop_reason = ("failed", "WhatsApp disconnected")

    if sent:
        offer_service.update_offer_admin(offer["id"], {"status": "sent"})
        _finish_run(run["id"], "completed", stop_reason[1] if stop_reason else None)
        return "completed"

    _finish_run(run["id"], "failed", stop_reason[1] if stop_reason else "No message was sent")
    return "failed"

def list_runs(page: int, per_page: int) -> tuple[list[dict], int]:
    start = (page - 1) * per_page

    response = (
        get_user_supabase()
        .table("dispatch_runs")
        .select("*, dispatches(status)", count="exact")
        .order("scheduled_for", desc=True)
        .range(start, start + per_page - 1)
        .execute()
    )

    runs = []

    for run in response.data:
        statuses = [dispatch["status"] for dispatch in run.pop("dispatches", [])]
        runs.append({**run, "summary": {status: statuses.count(status) for status in ("pending", "sent", "failed", "skipped")}})

    return runs, response.count or 0

def get_run(run_id: str) -> dict | None:
    response = (
        get_user_supabase()
        .table("dispatch_runs")
        .select("*, dispatches(*)")
        .eq("id", run_id)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def list_dispatches(status: str | None, page: int, per_page: int) -> tuple[list[dict], int]:
    start = (page - 1) * per_page

    query = (
        get_user_supabase()
        .table("dispatches")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(start, start + per_page - 1)
    )

    if status:
        query = query.eq("status", status)

    response = query.execute()

    return response.data, response.count or 0

def get_dispatch(dispatch_id: str) -> dict | None:
    response = (
        get_user_supabase()
        .table("dispatches")
        .select("*")
        .eq("id", dispatch_id)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def retry_dispatch(dispatch: dict, instance: dict, group: dict, offer: dict) -> dict:
    success, attempts, error = _send_with_retry(
        instance,
        group,
        offer_service.render_message(offer),
        offer_service.get_image_url(offer.get("image_path")),
        lambda seconds: bool(time.sleep(seconds))
    )

    data = {"attempts": dispatch["attempts"] + attempts}
    data.update({"status": "sent", "error": None, "sent_at": _now().isoformat()} if success else {"status": "failed", "error": error})

    response = get_supabase_admin().table("dispatches").update(data).eq("id", dispatch["id"]).execute()

    return response.data[0]