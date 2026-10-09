from src.extensions import limiter

from flask import Blueprint, jsonify, Response

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
@limiter.limit("50 per minute")
def health_check() -> Response:
    return jsonify({"status": "healthy"}), 200
