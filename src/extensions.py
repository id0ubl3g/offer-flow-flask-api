from config.providers.initialize_supabase import initialize_supabase_admin
from config.providers.initialize_redis import initialize_redis
from config.providers.initialize_limiter import initialize_limiter

from src.utils.system_utils import user_or_ip

from flask import Flask, current_app, g
from supabase import Client
from redis import Redis

limiter = initialize_limiter(user_or_ip)

def init_extensions(app: Flask) -> None:
    app.extensions["supabase_admin"] = initialize_supabase_admin()
    app.extensions["redis"] = initialize_redis()

    limiter.init_app(app)

def get_supabase_admin() -> Client:
    return current_app.extensions["supabase_admin"]

def get_user_supabase() -> Client:
    return g.supabase

def get_redis() -> Redis:
    return current_app.extensions["redis"]