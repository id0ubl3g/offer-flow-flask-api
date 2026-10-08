from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.utils.return_responses import create_error_response, create_internal_error_response

from flask import Blueprint, jsonify, Response, g

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile", methods=["GET"])
@require_auth
@limiter.limit("20 per minute")
def profile() -> Response:
    try:
        return jsonify({"user": g.user}), 200

    except Exception:
        return create_internal_error_response()