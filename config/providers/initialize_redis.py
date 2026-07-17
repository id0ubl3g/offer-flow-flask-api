from dotenv import load_dotenv
from redis import Redis
import os

load_dotenv()

def initialize_redis() -> Redis:
    redis_url = os.getenv("REDIS_URL")

    redis_client = Redis.from_url(
        redis_url,
        decode_responses=True
    )

    redis_client.ping()

    return redis_client