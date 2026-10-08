from config.providers.initialize_supabase import initialize_supabase

from src.services.auth_service import get_profile

from supabase_auth.errors import AuthApiError
from flask import request, jsonify, g
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
            supabase = initialize_supabase(access_token)
            response = supabase.auth.get_user(access_token)

            if response.user is None:
                return jsonify({"error": "Invalid access token."}), 401

            profile = get_profile(response.user.id)

            if not profile:
                return jsonify({"error": "Profile not found."}), 404

            g.supabase = supabase
            g.user = {
                **profile,
                "email": response.user.email
            }

        except AuthApiError:
            return jsonify({"error": "Invalid or expired access token."}), 401

        except Exception:
            return jsonify({"error": "Internal server error."}), 500

        return f(*args, **kwargs)

    return wrapper