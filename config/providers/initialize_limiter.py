from flask_limiter import Limiter
from dotenv import load_dotenv
import os

load_dotenv()

def initialize_limiter(key_func) -> Limiter:
    redis_url = os.getenv("REDIS_URL")

    limiter = Limiter(
        key_func=key_func,
        default_limits=["100 per minute"],
        storage_uri=redis_url
    )

    return limiter