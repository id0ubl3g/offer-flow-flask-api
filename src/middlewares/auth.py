from flask import request, jsonify, g
from functools import wraps
from supabase import Client
from typing import Callable

def require_auth(supabase: Client) -> Callable:
    def decorator(f):
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
                response = supabase.auth.get_user(access_token)

                if response.user is None:
                    return jsonify({"error": "Invalid access token."}), 401

                profile = (
                    supabase
                    .table("profiles")
                    .select("*")
                    .eq("id", response.user.id)
                    .single()
                    .execute()
                )

                if not profile.data:
                    return jsonify({"error": "Profile not found."}), 404

                g.user = {
                    **profile.data,
                    "email": response.user.email
                }

            except AuthApiError:
                return jsonify({"error": "Invalid or expired access token."}), 401

            except Exception:
                return jsonify({"error": "Internal server error."}), 500

            return f(*args, **kwargs)

        return wrapper

    return decorator