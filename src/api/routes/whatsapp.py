from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.schemas.offer_schema import format_validation_error
from src.schemas.whatsapp_schema import GroupUpdate
from src.services import whatsapp_service
from src.services.evolution_client import EvolutionError
from src.utils.return_responses import create_error_response, create_internal_error_response

from flask import Blueprint, request, jsonify, Response, g
from pydantic import ValidationError
from uuid import UUID

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")

def evolution_error_response(error: EvolutionError) -> tuple[Response, int]:
    return create_error_response(f"WhatsApp service error: {error.message}", 504 if error.status_code == 504 else 502)

@whatsapp_bp.route("", methods=["GET"])
@require_auth
@limiter.limit("30 per minute")
def get_whatsapp() -> Response:
    try:
        instance = whatsapp_service.get_instance(g.user["id"])

        if instance is None:
            return create_error_response("WhatsApp is not connected", 404)

        if instance["status"] != "open":
            try:
                instance = whatsapp_service.refresh_status(instance)

            except EvolutionError:
                pass

        qrcode = whatsapp_service.get_qrcode(instance["instance_name"]) if instance["status"] == "connecting" else None

        return jsonify({
            "instance": whatsapp_service.serialize_instance(instance),
            "qrcode": qrcode
        }), 200

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("/connect", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def connect_whatsapp() -> Response:
    try:
        instance = whatsapp_service.get_instance(g.user["id"])

        if instance and instance["status"] == "open":
            return create_error_response("WhatsApp is already connected", 409)

        instance, qrcode = whatsapp_service.connect(g.user["id"])

        return jsonify({
            "message": "Scan the QR code with WhatsApp to connect.",
            "instance": whatsapp_service.serialize_instance(instance),
            "qrcode": qrcode
        }), 200

    except EvolutionError as e:
        return evolution_error_response(e)

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("/disconnect", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def disconnect_whatsapp() -> Response:
    try:
        instance = whatsapp_service.get_instance(g.user["id"])

        if instance is None:
            return create_error_response("WhatsApp is not connected", 404)

        instance = whatsapp_service.disconnect(instance)

        return jsonify({
            "message": "WhatsApp disconnected successfully.",
            "instance": whatsapp_service.serialize_instance(instance)
        }), 200

    except EvolutionError as e:
        return evolution_error_response(e)

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("", methods=["DELETE"])
@require_auth
@limiter.limit("5 per minute")
def delete_whatsapp() -> Response:
    try:
        instance = whatsapp_service.get_instance(g.user["id"])

        if instance is None:
            return create_error_response("WhatsApp is not connected", 404)

        whatsapp_service.delete(instance)

        return jsonify({"message": "WhatsApp removed successfully."}), 200

    except EvolutionError as e:
        return evolution_error_response(e)

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("/groups/sync", methods=["POST"])
@require_auth
@limiter.limit("3 per minute")
def sync_groups() -> Response:
    try:
        instance = whatsapp_service.get_instance(g.user["id"])

        if instance is None:
            return create_error_response("WhatsApp is not connected", 404)

        instance = whatsapp_service.refresh_status(instance)

        if instance["status"] != "open":
            return create_error_response("WhatsApp must be connected to sync groups", 409)

        groups = whatsapp_service.sync_groups(instance)

        return jsonify({
            "message": "Groups synced successfully.",
            "groups": groups
        }), 200

    except EvolutionError as e:
        return evolution_error_response(e)

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("/groups", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def list_groups() -> Response:
    try:
        active = request.args.get("active")

        if active not in (None, "true", "false"):
            return create_error_response("active must be true or false", 400)

        groups = whatsapp_service.list_groups(g.user["id"], None if active is None else active == "true")

        return jsonify({"groups": groups}), 200

    except Exception:
        return create_internal_error_response()

@whatsapp_bp.route("/groups/<uuid:group_id>", methods=["PATCH"])
@require_auth
@limiter.limit("60 per minute")
def update_group(group_id: UUID) -> Response:
    try:
        payload = GroupUpdate.model_validate(request.get_json(silent=True) or {})

        group = whatsapp_service.get_group(g.user["id"], str(group_id))

        if group is None:
            return create_error_response("Group not found", 404)

        if payload.active and not group["can_send"]:
            return create_error_response("Only admins can send messages to this group", 400)

        group = whatsapp_service.set_group_active(group["id"], payload.active)

        return jsonify({
            "message": "Group updated successfully.",
            "group": {key: group[key] for key in ("id", "jid", "name", "can_send", "active")}
        }), 200

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_internal_error_response()