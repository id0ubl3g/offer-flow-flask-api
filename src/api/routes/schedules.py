from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.schemas.offer_schema import format_validation_error
from src.schemas.schedule_schema import ScheduleCreate, ScheduleUpdate, DispatchSettingsUpdate
from src.services import schedule_service
from src.utils.return_responses import create_error_response

from flask import Blueprint, request, jsonify, Response, g
from pydantic import ValidationError
from uuid import UUID

schedules_bp = Blueprint("schedules", __name__)

@schedules_bp.route("/schedules", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def list_schedules() -> Response:
    try:
        return jsonify({"schedules": [schedule_service.serialize_schedule(schedule) for schedule in schedule_service.list_schedules()]}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@schedules_bp.route("/schedules", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def create_schedule() -> Response:
    try:
        payload = ScheduleCreate.model_validate(request.get_json(silent=True) or {})

        if schedule_service.find_schedule_by_time(payload.send_time):
            return create_error_response("A schedule already exists at this time", 409)

        schedule = schedule_service.create_schedule(g.user["id"], payload.model_dump())

        return jsonify({
            "message": "Schedule created successfully.",
            "schedule": schedule_service.serialize_schedule(schedule)
        }), 201

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@schedules_bp.route("/schedules/<uuid:schedule_id>", methods=["PATCH"])
@require_auth
@limiter.limit("30 per minute")
def update_schedule(schedule_id: UUID) -> Response:
    try:
        payload = ScheduleUpdate.model_validate(request.get_json(silent=True) or {})
        data = payload.model_dump(exclude_unset=True)

        if not data:
            return create_error_response("No fields to update", 400)

        if schedule_service.get_schedule(str(schedule_id)) is None:
            return create_error_response("Schedule not found", 404)

        if "send_time" in data:
            existing = schedule_service.find_schedule_by_time(data["send_time"])

            if existing and existing["id"] != str(schedule_id):
                return create_error_response("A schedule already exists at this time", 409)

        schedule = schedule_service.update_schedule(str(schedule_id), data)

        return jsonify({
            "message": "Schedule updated successfully.",
            "schedule": schedule_service.serialize_schedule(schedule)
        }), 200

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@schedules_bp.route("/schedules/<uuid:schedule_id>", methods=["DELETE"])
@require_auth
@limiter.limit("30 per minute")
def delete_schedule(schedule_id: UUID) -> Response:
    try:
        if schedule_service.get_schedule(str(schedule_id)) is None:
            return create_error_response("Schedule not found", 404)

        schedule_service.delete_schedule(str(schedule_id))

        return jsonify({"message": "Schedule deleted successfully."}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@schedules_bp.route("/dispatch-settings", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def get_dispatch_settings() -> Response:
    try:
        return jsonify({"settings": schedule_service.get_settings(g.user["id"])}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@schedules_bp.route("/dispatch-settings", methods=["PATCH"])
@require_auth
@limiter.limit("30 per minute")
def update_dispatch_settings() -> Response:
    try:
        payload = DispatchSettingsUpdate.model_validate(request.get_json(silent=True) or {})
        data = payload.model_dump(exclude_unset=True)

        if not data:
            return create_error_response("No fields to update", 400)

        settings = {**schedule_service.get_settings(g.user["id"]), **data}

        if settings["min_delay_seconds"] > settings["max_delay_seconds"]:
            return create_error_response("min_delay_seconds must be less than or equal to max_delay_seconds", 400)

        return jsonify({
            "message": "Dispatch settings updated successfully.",
            "settings": schedule_service.save_settings(g.user["id"], settings)
        }), 200

    except ValidationError as e:
        return create_error_response(format_validation_error(e), 400)

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)