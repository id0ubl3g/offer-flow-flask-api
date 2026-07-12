from supabase import Client, create_client
from dotenv import load_dotenv
import os

load_dotenv()

def initialize_supabase() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    client = create_client(supabase_url, supabase_key)

    return client