from supabase import Client, ClientOptions, create_client
from dotenv import load_dotenv
import os

load_dotenv()

def _client_options() -> ClientOptions:
    return ClientOptions(auto_refresh_token=False, persist_session=False)

def initialize_supabase(access_token: str | None = None) -> Client:
    options = _client_options()

    if access_token:
        options.headers["Authorization"] = f"Bearer {access_token}"

    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY"),
        options
    )

def initialize_supabase_admin() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        _client_options()
    )