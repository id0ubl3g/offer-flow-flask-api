from src.extensions import limiter
from src.middlewares.auth import require_auth
from src.services import auth_service
from src.utils.system_utils import validate_user_data, is_valid_email
from src.utils.send_email_verification import SendEmailVerification
from src.utils.return_responses import create_error_response

from flask import Blueprint, request, jsonify, Response, g

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register() -> Response:
    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            return create_error_response(f'Missing required fields: {", ".join(["name", "email", "password"])}', 400)

        validation_error = validate_user_data({
            "name": name,
            "password": password,
        })

        if validation_error:
            return create_error_response(validation_error, 400)

        if not is_valid_email(email):
            return create_error_response('Invalid email format', 400)

        if auth_service.find_profile_id_by_email(email):
            return create_error_response("Email is already registered", 409)

        user = auth_service.register_user(name, email, password)

        if user is None:
            return create_error_response("Unable to create user", 400)

        return jsonify({
            "message": "User created successfully.",
            "user": user
        }), 201

    except Exception:
        return create_error_response('An error occurred while processing the request', 500)

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login() -> Response:
    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return create_error_response(f'Missing required fields: {", ".join(["email", "password"])}', 400)

        validation_error = validate_user_data({
            "password": password,
        })

        if validation_error:
            return create_error_response(validation_error, 400)

        if not is_valid_email(email):
            return create_error_response('Invalid email format', 400)

        session = auth_service.login_user(email, password)

        if session is None:
            return create_error_response("Invalid email or password", 401)

        return jsonify({
            "message": "Login successful.",
            **session
        }), 200

    except Exception as e:
        if "Invalid login credentials" in str(e):
            return create_error_response("Invalid email or password", 401)

        return create_error_response('An error occurred while processing the request', 500)

@auth_bp.route("/refresh", methods=["POST"])
@limiter.limit("5 per minute")
def refresh() -> Response:
    try:
        data = request.get_json(silent=True) or {}

        refresh_token = data.get("refresh_token")

        if not refresh_token:
            return create_error_response("Missing required fields: refresh_token", 400)

        session = auth_service.refresh_session(refresh_token)

        if session is None:
            return create_error_response("Invalid refresh token", 401)

        return jsonify({
            "message": "Session refreshed successfully.",
            **session
        }), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)

@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per minute")
def forgot_password() -> Response:
    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email")

        if not email:
            return create_error_response(f'Missing required fields: {", ".join(["email"])}', 400)

        if not is_valid_email(email):
            return create_error_response('Invalid email format', 400)

        generic_response = jsonify({"message": "If an account exists for this email, a recovery code has been sent"}), 200

        user_id = auth_service.find_profile_id_by_email(email)

        if user_id is None:
            return generic_response

        code = auth_service.create_password_reset_code(user_id)

        SendEmailVerification().send_verification_email(email, code, 'reset_password')

        return generic_response

    except Exception:
        return create_error_response('An error occurred while processing the request', 500)

@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password() -> Response:
    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email")
        password = data.get("password")
        code = data.get("code")

        if not email or not password or not code:
            return create_error_response("Missing required fields: email, password, code", 400)

        code = code.strip().upper()

        if not is_valid_email(email):
            return create_error_response('Invalid email format', 400)

        validation_error = validate_user_data({
            "password": password,
            "code": code
        })

        if validation_error:
            return create_error_response(validation_error, 400)

        user_id = auth_service.find_profile_id_by_email(email)

        if user_id is None or not auth_service.is_valid_password_reset_code(user_id, code):
            return create_error_response("Invalid or expired recovery code", 400)

        auth_service.reset_password(user_id, password)

        return jsonify({"message": "Password updated successfully"}), 200

    except Exception:
        return create_error_response('An error occurred while processing the request', 500)

@auth_bp.route("/delete-account", methods=["DELETE"])
@require_auth
@limiter.limit("5 per minute")
def delete_account() -> Response:
    try:
        auth_service.delete_account(g.user["id"])

        return jsonify({"message": "Account deleted successfully."}), 200

    except Exception:
        return create_error_response("An error occurred while processing the request", 500)