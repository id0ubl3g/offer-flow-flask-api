from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.services import dispatch_service, offer_service, whatsapp_service
from src.services.evolution_client import EvolutionError
from src.utils.return_responses import create_error_response, create_internal_error_response

from flask import Blueprint, request, jsonify, Response, g
from uuid import UUID

dispatches_bp = Blueprint("dispatches", __name__)

DISPATCH_STATUSES = ("pending", "sent", "failed", "skipped")

def read_pagination() -> tuple[int, int] | None:
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if page < 1 or not 1 <= per_page <= 100:
        return None

    return page, per_page

@dispatches_bp.route("/dispatch-runs", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def list_runs() -> Response:
    try:
        pagination = read_pagination()

        if pagination is None:
            return create_error_response("page must be >= 1 and per_page between 1 and 100", 400)

        runs, total = dispatch_service.list_runs(*pagination)

        return jsonify({"runs": runs, "page": pagination[0], "per_page": pagination[1], "total": total}), 200

    except Exception:
        return create_internal_error_response()

@dispatches_bp.route("/dispatch-runs/<uuid:run_id>", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def get_run(run_id: UUID) -> Response:
    try:
        run = dispatch_service.get_run(str(run_id))

        if run is None:
            return create_error_response("Run not found", 404)

        return jsonify({"run": run}), 200

    except Exception:
        return create_internal_error_response()

@dispatches_bp.route("/dispatches", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def list_dispatches() -> Response:
    try:
        status = request.args.get("status")
        pagination = read_pagination()

        if status and status not in DISPATCH_STATUSES:
            return create_error_response(f"Invalid status. Allowed: {', '.join(DISPATCH_STATUSES)}", 400)

        if pagination is None:
            return create_error_response("page must be >= 1 and per_page between 1 and 100", 400)

        dispatches, total = dispatch_service.list_dispatches(status, *pagination)

        return jsonify({"dispatches": dispatches, "page": pagination[0], "per_page": pagination[1], "total": total}), 200

    except Exception:
        return create_internal_error_response()

@dispatches_bp.route("/dispatches/<uuid:dispatch_id>/retry", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def retry_dispatch(dispatch_id: UUID) -> Response:
    try:
        dispatch = dispatch_service.get_dispatch(str(dispatch_id))

        if dispatch is None:
            return create_error_response("Dispatch not found", 404)

        if dispatch["status"] not in ("failed", "skipped"):
            return create_error_response("Only failed or skipped dispatches can be retried", 409)

        offer = offer_service.get_offer(dispatch["offer_id"]) if dispatch["offer_id"] else None
        group = whatsapp_service.get_group(g.user["id"], dispatch["group_id"]) if dispatch["group_id"] else None

        if offer is None or group is None:
            return create_error_response("The offer or group of this dispatch no longer exists", 409)

        if not group["can_send"]:
            return create_error_response("Only admins can send messages to this group", 400)

        instance = whatsapp_service.get_instance(g.user["id"])

        if instance is None or instance["status"] != "open":
            return create_error_response("WhatsApp must be connected to send offers", 409)

        dispatch = dispatch_service.retry_dispatch(dispatch, instance, group, offer)

        if dispatch["status"] != "sent":
            return create_error_response(f"WhatsApp service error: {dispatch['error']}", 502)

        return jsonify({"message": f"Offer sent to {group['name']}.", "dispatch": dispatch}), 200

    except EvolutionError as e:
        return create_error_response(f"WhatsApp service error: {e.message}", 504 if e.status_code == 504 else 502)

    except Exception:
        return create_internal_error_response()