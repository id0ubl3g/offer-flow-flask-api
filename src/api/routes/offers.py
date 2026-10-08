from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.schemas.offer_schema import OfferCreate, OfferUpdate, format_validation_error
from src.services import offer_service
from src.utils.return_responses import create_error_response

from flask import Blueprint, request, jsonify, Response, g
from pydantic import ValidationError
from werkzeug.exceptions import RequestEntityTooLarge
from uuid import UUID

offers_bp = Blueprint("offers", __name__, url_prefix="/offers")

OFFER_STATUSES = ("draft", "queued", "sent", "archived")

@offers_bp.route("", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def list_offers() -> Response:
    try:
        status = request.args.get("status")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        if status and status not in OFFER_STATUSES:
            return create_error_response(f"Invalid status. Allowed: {', '.join(OFFER_STATUSES)}", 400)

        if page < 1 or not 1 <= per_page <= 100:
            return create_error_response("page must be >= 1 and per_page between 1 and 100", 400)

        offers, total = offer_service.list_offers(status, page, per_page)

        return jsonify({
            "offers": [offer_service.serialize_offer(offer) for offer in offers],
            "page": page,
            "per_page": per_page,
            "total": total
        }), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def create_offer() -> Response:
    try:
        payload = OfferCreate.model_validate(request.get_json(silent=True) or {})

        offer = offer_service.create_offer(g.user["id"], payload.model_dump())

        return jsonify({
            "message": "Offer created successfully.",
            "offer": offer_service.serialize_offer(offer)
        }), 201

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def get_offer(offer_id: UUID) -> Response:
    try:
        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        return jsonify({"offer": offer_service.serialize_offer(offer)}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>", methods=["PATCH"])
@require_auth
@limiter.limit("30 per minute")
def update_offer(offer_id: UUID) -> Response:
    try:
        payload = OfferUpdate.model_validate(request.get_json(silent=True) or {})
        data = payload.model_dump(exclude_unset=True)

        if not data:
            return create_error_response("No fields to update", 400)

        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        original_price_cents = data.get("original_price_cents", offer["original_price_cents"])
        price_cents = data.get("price_cents", offer["price_cents"])

        if price_cents > original_price_cents:
            return create_error_response("price_cents must be less than or equal to original_price_cents", 400)

        updated = offer_service.update_offer(str(offer_id), data)

        if updated is None:
            return create_error_response("Offer not found", 404)

        return jsonify({
            "message": "Offer updated successfully.",
            "offer": offer_service.serialize_offer(updated)
        }), 200

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>", methods=["DELETE"])
@require_auth
@limiter.limit("30 per minute")
def delete_offer(offer_id: UUID) -> Response:
    try:
        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        offer_service.delete_offer(offer)

        return jsonify({"message": "Offer deleted successfully."}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>/preview", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def preview_offer(offer_id: UUID) -> Response:
    try:
        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        return jsonify({
            "message": offer_service.render_message(offer),
            "image_url": offer_service.get_image_url(offer.get("image_path"))
        }), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>/image", methods=["PUT"])
@require_auth
@limiter.limit("10 per minute")
def upload_offer_image(offer_id: UUID) -> Response:
    try:
        file = request.files.get("image")

        if file is None:
            return create_error_response("Missing required file: image", 400)

        content = file.read(offer_service.MAX_IMAGE_SIZE + 1)

        if len(content) > offer_service.MAX_IMAGE_SIZE:
            return create_error_response("Image must be at most 5 MB", 413)

        image_type = offer_service.detect_image_type(content)

        if image_type is None:
            return create_error_response("Image must be JPEG, PNG or WEBP", 400)

        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        updated = offer_service.set_offer_image(offer, content, *image_type)

        return jsonify({
            "message": "Image uploaded successfully.",
            "offer": offer_service.serialize_offer(updated)
        }), 200

    except RequestEntityTooLarge:
        return create_error_response("Image must be at most 5 MB", 413)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@offers_bp.route("/<uuid:offer_id>/image", methods=["DELETE"])
@require_auth
@limiter.limit("10 per minute")
def delete_offer_image(offer_id: UUID) -> Response:
    try:
        offer = offer_service.get_offer(str(offer_id))

        if offer is None:
            return create_error_response("Offer not found", 404)

        updated = offer_service.remove_offer_image(offer)

        return jsonify({
            "message": "Image removed successfully.",
            "offer": offer_service.serialize_offer(updated)
        }), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)