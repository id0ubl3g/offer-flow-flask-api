from src.extensions import limiter
from src.services import whatsapp_service
from src.utils.return_responses import create_error_response, create_internal_error_response

from flask import Blueprint, request, jsonify, Response
import hmac

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")

@webhooks_bp.route("/evolution", methods=["POST"])
@limiter.exempt
def evolution_webhook() -> Response:
    try:
        payload = request.get_json(silent=True) or {}

        instance_name = payload.get("instance")
        secret = request.headers.get("x-webhook-secret", "")

        if not isinstance(instance_name, str) or not hmac.compare_digest(secret, whatsapp_service.webhook_secret_for(instance_name)):
            return create_error_response("Unauthorized", 401)

        instance = whatsapp_service.get_instance_by_name(instance_name)

        if instance is None:
            return jsonify({"received": True}), 200

        event = payload.get("event")
        data = payload.get("data") or {}

        if event == "qrcode.updated":
            whatsapp_service.save_qrcode(instance_name, data.get("qrcode"))

        elif event == "connection.update":
            whatsapp_service.apply_connection_state(instance, data.get("state"))

        return jsonify({"received": True}), 200

    except Exception:
        return create_internal_error_response()