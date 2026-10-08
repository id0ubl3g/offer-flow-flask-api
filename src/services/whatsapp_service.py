from src.extensions import get_supabase_admin, get_redis, get_evolution

from datetime import datetime, timezone
from dotenv import load_dotenv
import hashlib
import hmac
import os

load_dotenv()

QRCODE_TTL = 60
INSTANCE_STATUSES = ("connecting", "open", "close")
IMAGE_MIMETYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _jid_number(jid: str | None) -> str | None:
    if not jid:
        return None

    return jid.split("@", 1)[0].split(":", 1)[0]

def instance_name_for(user_id: str) -> str:
    return f"of-{user_id}"

def webhook_secret_for(instance_name: str) -> str:
    secret = os.getenv("EVOLUTION_WEBHOOK_SECRET")

    if not secret:
        raise RuntimeError("EVOLUTION_WEBHOOK_SECRET is not configured")

    return hmac.new(
        secret.encode(),
        instance_name.encode(),
        hashlib.sha256
    ).hexdigest()

def webhook_url() -> str:
    return os.getenv("APP_WEBHOOK_BASE_URL", "http://host.docker.internal:5000").rstrip("/") + "/webhooks/evolution"

def serialize_instance(instance: dict) -> dict:
    return {
        key: instance.get(key)
        for key in ("id", "status", "phone", "profile_name", "connected_at", "created_at")
    }

def get_instance(user_id: str) -> dict | None:
    response = (
        get_supabase_admin()
        .table("whatsapp_instances")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def get_instance_by_name(instance_name: str) -> dict | None:
    response = (
        get_supabase_admin()
        .table("whatsapp_instances")
        .select("*")
        .eq("instance_name", instance_name)
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def update_instance(instance_id: str, data: dict) -> dict:
    response = (
        get_supabase_admin()
        .table("whatsapp_instances")
        .update(data)
        .eq("id", instance_id)
        .execute()
    )

    return response.data[0]

def save_qrcode(instance_name: str, qrcode: dict | None) -> str | None:
    base64 = (qrcode or {}).get("base64")

    if base64:
        get_redis().setex(f"whatsapp_qrcode:{instance_name}", QRCODE_TTL, base64)

    return base64

def get_qrcode(instance_name: str) -> str | None:
    return get_redis().get(f"whatsapp_qrcode:{instance_name}")

def connect(user_id: str) -> tuple[dict, str | None]:
    instance = get_instance(user_id)

    if instance is None:
        instance_name = instance_name_for(user_id)

        created = get_evolution().create_instance(instance_name, webhook_url(), webhook_secret_for(instance_name))

        response = (
            get_supabase_admin()
            .table("whatsapp_instances")
            .insert({
                "user_id": user_id,
                "instance_name": instance_name,
                "instance_token": created["hash"],
                "status": "connecting"
            })
            .execute()
        )

        return response.data[0], save_qrcode(instance_name, created.get("qrcode"))

    qrcode = get_evolution().connect(instance["instance_name"])
    instance = update_instance(instance["id"], {"status": "connecting"})

    return instance, save_qrcode(instance["instance_name"], qrcode)

def apply_connection_state(instance: dict, state: str) -> dict:
    if state not in INSTANCE_STATUSES or state == instance["status"]:
        return instance

    data = {"status": state}

    if state == "open":
        details = get_evolution().fetch_instance(instance["instance_name"]) or {}

        data["phone"] = _jid_number(details.get("ownerJid"))
        data["profile_name"] = details.get("profileName")
        data["connected_at"] = _now()

        get_redis().delete(f"whatsapp_qrcode:{instance['instance_name']}")

    return update_instance(instance["id"], data)

def refresh_status(instance: dict) -> dict:
    return apply_connection_state(instance, get_evolution().connection_state(instance["instance_name"]))

def disconnect(instance: dict) -> dict:
    get_evolution().logout(instance["instance_name"])

    return update_instance(instance["id"], {"status": "close"})

def delete(instance: dict) -> None:
    get_evolution().delete_instance(instance["instance_name"])

    get_supabase_admin().table("whatsapp_instances").delete().eq("id", instance["id"]).execute()
    get_redis().delete(f"whatsapp_qrcode:{instance['instance_name']}")

def _is_admin(group: dict, owner_jid: str | None) -> bool | None:
    owner_number = _jid_number(owner_jid)
    participants = group.get("participants")

    if not owner_number or not participants:
        return None

    for participant in participants:
        candidates = (participant.get("id"), participant.get("jid"), participant.get("phoneNumber"))

        if owner_number in {_jid_number(candidate) for candidate in candidates if candidate}:
            return participant.get("admin") in ("admin", "superadmin")

    return None

def sync_groups(instance: dict) -> list[dict]:
    details = get_evolution().fetch_instance(instance["instance_name"]) or {}
    fetched = get_evolution().fetch_groups(instance["instance_name"])
    synced_at = _now()

    rows = [
        {
            "user_id": instance["user_id"],
            "instance_id": instance["id"],
            "jid": group["id"],
            "name": group.get("subject") or group["id"],
            "participants_count": group.get("size"),
            "is_announce": bool(group.get("announce")),
            "is_admin": _is_admin(group, details.get("ownerJid")),
            "removed_at": None,
            "synced_at": synced_at
        }
        for group in fetched
        if str(group.get("id", "")).endswith("@g.us")
    ]

    admin = get_supabase_admin()

    if rows:
        admin.table("groups").upsert(rows, on_conflict="instance_id,jid").execute()

    (
        admin.table("groups")
        .update({"removed_at": synced_at, "active": False})
        .eq("instance_id", instance["id"])
        .lt("synced_at", synced_at)
        .is_("removed_at", "null")
        .execute()
    )

    return list_groups(instance["user_id"])

def list_groups(user_id: str, active: bool | None = None) -> list[dict]:
    query = (
        get_supabase_admin()
        .table("groups")
        .select("id, jid, name, participants_count, is_announce, is_admin, can_send, active, removed_at, synced_at")
        .eq("user_id", user_id)
        .is_("removed_at", "null")
        .order("name")
    )

    if active is not None:
        query = query.eq("active", active)

    return query.execute().data

def get_group(user_id: str, group_id: str) -> dict | None:
    response = (
        get_supabase_admin()
        .table("groups")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", group_id)
        .is_("removed_at", "null")
        .maybe_single()
        .execute()
    )

    return response.data if response else None

def set_group_active(group_id: str, active: bool) -> dict:
    response = (
        get_supabase_admin()
        .table("groups")
        .update({"active": active})
        .eq("id", group_id)
        .execute()
    )

    return response.data[0]

def send_offer(instance: dict, group: dict, message: str, image_url: str | None) -> dict:
    if image_url:
        extension = image_url.rsplit(".", 1)[-1].lower()

        return get_evolution().send_image(
            instance["instance_name"],
            group["jid"],
            image_url,
            IMAGE_MIMETYPES.get(extension, "image/jpeg"),
            message
        )

    return get_evolution().send_text(instance["instance_name"], group["jid"], message)