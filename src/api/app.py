from config.providers.initialize_supabase import initialize_supabase
from src.utils.system_utils import validate_user_data, is_valid_email
from src.middlewares.auth import require_auth

from flask import Flask, request, jsonify, Response, g
from datetime import datetime, timezone, timedelta
# from flask_cors import CORS

class Server:
    def __init__(self) -> None:
        self.app: Flask = Flask(__name__)

        self.supabase = initialize_supabase()

        # CORS(
        #     self.app,
        #     origins="*",
        #     allow_headers=["Content-Type", "Authorization"],
        #     methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
        # )

        self._register_routes()

    def create_error_response(self, message: str, code: int) -> Response:
        return jsonify({'error': message}), code

    def _register_routes(self) -> None:
        @self.app.route("/auth/register", methods=["POST"])
        def auth_register() -> Response:
            try:
                data = request.get_json()

                name = data.get("name")
                email = data.get("email")
                password = data.get("password")

                if not name or not email or not password:
                    return self.create_error_response(f'Missing required fields: {", ".join(["name", "email", "password"])}', 400)

                validation_error = validate_user_data({
                    "name": name,
                    "password": password,
                })

                if validation_error:
                    return self.create_error_response(validation_error, 400)

                if not is_valid_email(email):
                    return self.create_error_response('Invalid email format', 400)

                response = self.supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })

                if response.user is None:
                    return self.create_error_response("Unable to create user.", 400)

                profile = self.supabase.table("profiles").insert({
                    "id": response.user.id,
                    "name": name
                }).execute()

                print(profile)

                return jsonify({
                    "message": "User created successfully.",
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "name": name
                    }
                }), 201

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route("/auth/login", methods=["POST"])
        def auth_login() -> Response:
            try:
                data = request.get_json()

                email = data.get("email")
                password = data.get("password")

                if not email or not password:
                    return self.create_error_response(f'Missing required fields: {", ".join(["email", "password"])}', 400)

                validation_error = validate_user_data({
                    "password": password,
                })

                if validation_error:
                    return self.create_error_response(validation_error, 400)

                if not is_valid_email(email):
                    return self.create_error_response('Invalid email format', 400)

                response = self.supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                if response.user is None or response.session is None:
                    return self.create_error_response(
                        "Invalid email or password.",
                        401
                    )

                profile = (
                    self.supabase
                    .table("profiles")
                    .select("*")
                    .eq("id", response.user.id)
                    .single()
                    .execute()
                )

                return jsonify({
                    "message": "Login successful.",
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "user": profile.data
                }), 200

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route("/auth/refresh", methods=["POST"])
        def auth_refresh() -> Response:
            try:
                data = request.get_json()

                refresh_token = data.get("refresh_token")

                if not refresh_token:
                    return self.create_error_response("Missing required fields: refresh_token", 400)

                response = self.supabase.auth.refresh_session(refresh_token)

                if response.session is None:
                    return self.create_error_response("Invalid refresh token.", 401)

                return jsonify({
                    "message": "Session refreshed successfully.",
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }), 200

            except Exception:
                return self.create_error_response("An error occurred while processing the request", 500)

        @self.app.route("/profile", methods=["GET"])
        @require_auth(self.supabase)
        def profile() -> Response:
            try:
                return jsonify({"user": g.user}), 200

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

    def run_production(self, host: str = '0.0.0.0', port: int = 5000) -> None:
        self.app.run(debug=False, host=host, port=port, use_reloader=False)


