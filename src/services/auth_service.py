from config.providers.initialize_supabase import initialize_supabase

from src.extensions import get_supabase_admin, get_redis

import secrets

PASSWORD_RESET_TTL = 10 * 60
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def generate_code() -> str:
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))

def find_profile_id_by_email(email: str) -> str | None:
    profile = (
        get_supabase_admin()
        .table("profiles")
        .select("id")
        .eq("email", email)
        .maybe_single()
        .execute()
    )

    if profile is None or profile.data is None:
        return None

    return profile.data["id"]

def get_profile(user_id: str) -> dict | None:
    profile = (
        get_supabase_admin()
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if profile is None:
        return None

    return profile.data

def register_user(name: str, email: str, password: str) -> dict | None:
    response = initialize_supabase().auth.sign_up({
        "email": email,
        "password": password
    })

    if response.user is None:
        return None

    get_supabase_admin().table("profiles").insert({
        "id": response.user.id,
        "name": name,
        "email": email
    }).execute()

    return {
        "id": response.user.id,
        "email": response.user.email,
        "name": name
    }

def login_user(email: str, password: str) -> dict | None:
    response = initialize_supabase().auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    if response.user is None or response.session is None:
        return None

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": response.session.expires_at,
        "user": get_profile(response.user.id)
    }

def refresh_session(refresh_token: str) -> dict | None:
    response = initialize_supabase().auth.refresh_session(refresh_token)

    if response.session is None:
        return None

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": response.session.expires_at
    }

def create_password_reset_code(user_id: str) -> str:
    code = generate_code()

    get_redis().setex(f"password_reset:{user_id}", PASSWORD_RESET_TTL, code)

    return code

def is_valid_password_reset_code(user_id: str, code: str) -> bool:
    saved_code = get_redis().get(f"password_reset:{user_id}")

    return saved_code is not None and secrets.compare_digest(saved_code, code)

def reset_password(user_id: str, password: str) -> None:
    get_supabase_admin().auth.admin.update_user_by_id(
        user_id, {"password": password}
    )

    get_redis().delete(f"password_reset:{user_id}")

def delete_account(user_id: str) -> None:
    get_supabase_admin() \
        .table("profiles") \
        .delete() \
        .eq("id", user_id) \
        .execute()

    get_supabase_admin().auth.admin.delete_user(user_id)