from supabase import Client, create_client
from dotenv import load_dotenv
import os

load_dotenv()

def initialize_supabase() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )

def initialize_supabase_admin() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )