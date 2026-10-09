from src.extensions import get_user_supabase, get_supabase_admin

from datetime import datetime, timezone

import uuid
import re

BUCKET = "offer-images"
MAX_IMAGE_SIZE = 5 * 1024 * 1024
DEFAULT_TEMPLATE = "🔥 *{product_name}*\n\nDe ~R$ {original_price}~ por *R$ {price}*\n{discount}% OFF\n\n🛒 {url}"
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")

def format_brl(cents: int) -> str:
    reais, centavos = divmod(cents, 100)
    return f"{reais:,}".replace(",", ".") + f",{centavos:02d}"

def detect_image_type(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"

    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", "webp"

    return None

def get_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None

    return get_supabase_admin().storage.from_(BUCKET).get_public_url(image_path).rstrip("?")

def serialize_offer(offer: dict) -> dict:
    return {
        **offer,
        "image_url": get_image_url(offer.get("image_path"))
    }

def render_message(offer: dict) -> str:
    values = {
        "product_name": offer["product_name"],
        "price": format_brl(offer["price_cents"]),
        "original_price": format_brl(offer["original_price_cents"]),
        "discount": str(offer["discount_percent"]),
        "url": offer["url"]
    }

    template = offer.get("message") or DEFAULT_TEMPLATE

    return PLACEHOLDER_PATTERN.sub(lambda match: values.get(match.group(1), match.group(0)), template)

def list_offers(status: str | None, tag: str | None, page: int, per_page: int) -> tuple[list[dict], int]:
    start = (page - 1) * per_page

    query = (
        get_user_supabase()
        .table("offers")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(start, start + per_page - 1)
    )

    if status:
        query = query.eq("status", status)

    if tag:
        query = query.contains("tags", [tag])

    response = query.execute()

    return response.data, response.count or 0

def get_offer(offer_id: str) -> dict | None:
    response = (
        get_user_supabase()
        .table("offers")
        .select("*")
        .eq("id", offer_id)
        .maybe_single()
        .execute()
    )

    if response is None:
        return None

    return response.data

def create_offer(user_id: str, data: dict) -> dict:
    response = (
        get_user_supabase()
        .table("offers")
        .insert({**data, "user_id": user_id})
        .execute()
    )

    return response.data[0]

def update_offer(offer_id: str, data: dict) -> dict | None:
    response = (
        get_user_supabase()
        .table("offers")
        .update(data)
        .eq("id", offer_id)
        .execute()
    )

    return response.data[0] if response.data else None

def delete_offer(offer: dict) -> None:
    get_user_supabase().table("offers").delete().eq("id", offer["id"]).execute()

    if offer.get("image_path"):
        get_user_supabase().storage.from_(BUCKET).remove([offer["image_path"]])

def set_offer_image(offer: dict, content: bytes, content_type: str, extension: str) -> dict | None:
    storage = get_user_supabase().storage.from_(BUCKET)
    image_path = f"{offer['user_id']}/{offer['id']}/{uuid.uuid4().hex}.{extension}"

    storage.upload(image_path, content, {"content-type": content_type})

    try:
        updated = update_offer(offer["id"], {"image_path": image_path})

    except Exception:
        storage.remove([image_path])
        raise

    if offer.get("image_path"):
        storage.remove([offer["image_path"]])

    return updated

def remove_offer_image(offer: dict) -> dict | None:
    updated = update_offer(offer["id"], {"image_path": None})

    if offer.get("image_path"):
        get_user_supabase().storage.from_(BUCKET).remove([offer["image_path"]])

    return updated

def queue_offer(offer_id: str) -> dict | None:
    return update_offer(offer_id, {
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat()
    })

def unqueue_offer(offer_id: str) -> dict | None:
    return update_offer(offer_id, {"status": "draft", "queued_at": None})

def list_queue() -> list[dict]:
    response = (
        get_user_supabase()
        .table("offers")
        .select("*")
        .eq("status", "queued")
        .order("queued_at")
        .execute()
    )

    return response.data

def update_offer_admin(offer_id: str, data: dict) -> None:
    get_supabase_admin().table("offers").update(data).eq("id", offer_id).execute()