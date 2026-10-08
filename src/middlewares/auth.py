from config.providers.initialize_supabase import initialize_supabase

from src.extensions import get_supabase_admin
from src.services.auth_service import get_profile

from supabase_auth.errors import AuthError
from flask import request, jsonify, g, current_app
from functools import wraps
from typing import Callable

def require_auth(f: Callable) -> Callable:
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Authorization header is required."}), 401

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Invalid authorization header."}), 401

        access_token = auth_header.removeprefix("Bearer ").strip()
        g.access_token = access_token

        try:
            claims = get_supabase_admin().auth.get_claims(access_token)["claims"]

            if claims.get("role") != "authenticated" or not claims.get("sub"):
                return jsonify({"error": "Invalid access token."}), 401

            profile = get_profile(claims["sub"])

            if not profile:
                return jsonify({"error": "Profile not found."}), 404

            g.supabase = initialize_supabase(access_token)
            g.user = {
                **profile,
                "email": claims.get("email") or profile.get("email")
            }

        except (AuthError, ValueError):
            return jsonify({"error": "Invalid or expired access token."}), 401

        except Exception:
            current_app.logger.exception("Authentication failed unexpectedly")
            return jsonify({"error": "Internal server error."}), 500

        return f(*args, **kwargs)

    return wrapper