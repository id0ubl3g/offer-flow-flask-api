from config.providers.initialize_supabase import initialize_supabase, initialize_supabase_admin
from config.providers.initialize_redis import initialize_redis
from config.providers.initialize_limiter import initialize_limiter

from src.middlewares.auth import require_auth

from src.utils.system_utils import validate_user_data, is_valid_email, user_or_ip
from src.utils.send_email_verification import SendEmailVerification

from flask import Flask, request, jsonify, Response, g
from datetime import datetime, timezone, timedelta
# from flask_cors import CORS
import secrets
import math

class Server:
    def __init__(self) -> None:
        self.app: Flask = Flask(__name__)

        self.PASSWORD_RESET_TTL = 10 * 60

        self.supabase = initialize_supabase()
        self.supabase_admin = initialize_supabase_admin()
        self.redis = initialize_redis()
        self.limiter = initialize_limiter(self.app, user_or_ip)
        
        # CORS(
        #     self.app,
        #     origins="*",
        #     allow_headers=["Content-Type", "Authorization"],
        #     methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
        # )

        self._register_routes()

    def create_error_response(self, message: str, code: int) -> Response:
        return jsonify({'error': message}), code

    def generate_code(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return ''.join(secrets.choice(alphabet) for _ in range(6))

    def check_and_apply_block(self, current_user: str, increment: bool = True) -> Response | None:
        block_key = f"blocked:{current_user}"
        count_key = f"count429:{current_user}"
        
        ttl = self.redis.ttl(block_key)
        if ttl > 0:
            minutes = max(1, math.ceil(ttl / 60))
            return self.create_error_response(f"You have been temporarily blocked due to repeated rate limit violations. Please try again in {minutes} minute(s).", 403)
        
        count =  None
        
        if increment:
            pipe = self.redis.pipeline()
            pipe.incr(count_key)
            pipe.expire(count_key, 300)
            
            count, _ = pipe.execute()

        if increment and count == 3:
            return self.create_error_response("You are approaching the rate limit. One more failed attempt will block you for 30 minutes. Please try again later.", 429)

        if increment and count >= 4:
            self.redis.set(block_key, 1, ex=1800)
            self.redis.delete(count_key)
            
            return self.create_error_response("You have been temporarily blocked due to repeated rate limit violations.", 403)
        
        return None

    def _register_routes(self) -> None:
        @self.app.errorhandler(429)
        def ratelimit_error(e) -> Response:
            current_user = user_or_ip()
            response_check_and_apply_block = self.check_and_apply_block(current_user)

            if response_check_and_apply_block:
                return response_check_and_apply_block

            return self.create_error_response("Too many requests. Please try again later.", 429)

        @self.app.route("/auth/register", methods=["POST"])
        @self.limiter.limit("5 per minute")
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

                profile = (
                    self.supabase
                    .table("profiles")
                    .select("id")
                    .eq("email", email)
                    .limit(1)
                    .execute()
                )
                
                if profile.data:
                    return self.create_error_response("Email is already registered", 409)

                response = self.supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })

                if response.user is None:
                    return self.create_error_response("Unable to create user", 400)

                profile = self.supabase.table("profiles").insert({
                    "id": response.user.id,
                    "name": name,
                    "email": email
                }).execute()

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
        @self.limiter.limit("5 per minute")
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
                    return self.create_error_response("Invalid email or password", 401)

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

            except Exception as e:
                if "Invalid login credentials" in str(e):
                    return self.create_error_response("Invalid email or password", 401)

                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route("/auth/refresh", methods=["POST"])
        @self.limiter.limit("5 per minute")
        def auth_refresh() -> Response:
            try:
                data = request.get_json()

                refresh_token = data.get("refresh_token")

                if not refresh_token:
                    return self.create_error_response("Missing required fields: refresh_token", 400)

                response = self.supabase.auth.refresh_session(refresh_token)

                if response.session is None:
                    return self.create_error_response("Invalid refresh token", 401)

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
        @self.limiter.limit("20 per minute")
        def profile() -> Response:
            try:
                return jsonify({"user": g.user}), 200

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route('/auth/forgot-password', methods=['POST'])
        @self.limiter.limit("5 per minute")
        def auth_forgot_password() -> Response:
            try:
                data = request.get_json()

                email = data.get("email")

                if not email:
                    return self.create_error_response(f'Missing required fields: {", ".join(["email"])}', 400)

                if not is_valid_email(email):
                    return self.create_error_response('Invalid email format', 400)

                profile = (
                    self.supabase
                    .table("profiles")
                    .select("id")
                    .eq("email", email)
                    .maybe_single()
                    .execute()
                )

                generic_response = jsonify({"message": "If an account exists for this email, a recovery code has been sent"}), 200

                if profile is None or profile.data is None:
                    return generic_response

                user_id = profile.data["id"]

                key = f"password_reset:{user_id}"

                code = self.generate_code()

                self.redis.setex(key, self.PASSWORD_RESET_TTL, code)

                SendEmailVerification().send_verification_email(email, code, 'reset_password')

                return generic_response

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route("/auth/reset-password", methods=["POST"])
        @self.limiter.limit("5 per minute")
        def auth_reset_password() -> Response:
            try:
                data = request.get_json()

                email = data.get("email")
                password = data.get("password")
                code = data.get("code")

                if not email or not password or not code:
                    return self.create_error_response("Missing required fields: email, password, code", 400)

                code = code.strip().upper()

                if not is_valid_email(email):
                    return self.create_error_response('Invalid email format', 400)

                validation_error = validate_user_data({
                    "password": password,
                    "code": code
                })

                if validation_error:
                    return self.create_error_response(validation_error, 400)

                profile = (
                    self.supabase
                    .table("profiles")
                    .select("id")
                    .eq("email", email)
                    .maybe_single()
                    .execute()
                )

                if profile is None or profile.data is None:
                    return self.create_error_response("Invalid or expired recovery code", 400)

                user_id = profile.data["id"]

                key = f"password_reset:{user_id}"

                saved_code = self.redis.get(key)

                if saved_code is None or not secrets.compare_digest(saved_code, code):
                    return self.create_error_response("Invalid or expired recovery code", 400)

                self.supabase_admin.auth.admin.update_user_by_id(
                    user_id, {"password": password}
                )

                self.redis.delete(key)

                return jsonify({"message": "Password updated successfully"}), 200

            except Exception:
                return self.create_error_response('An error occurred while processing the request', 500)

        @self.app.route("/auth/delete-account", methods=["DELETE"])
        @require_auth(self.supabase)
        @self.limiter.limit("5 per minute")
        def auth_delete_account() -> Response:
            try:
                user_id = g.user["id"]

                self.supabase_admin \
                    .table("profiles") \
                    .delete() \
                    .eq("id", user_id) \
                    .execute()

                self.supabase_admin.auth.admin.delete_user(user_id)

                return jsonify({"message": "Account deleted successfully."}), 200

            except Exception:
                return self.create_error_response("An error occurred while processing the request", 500)

    def run_production(self, host: str = '0.0.0.0', port: int = 5000) -> None:
        self.app.run(debug=False, host=host, port=port, use_reloader=False)