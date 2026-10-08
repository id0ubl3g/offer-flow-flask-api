from src.utils.return_responses import create_error_response

from flask import Response
from redis import Redis
import math

BLOCK_TTL = 30 * 60
VIOLATION_WINDOW_TTL = 5 * 60

def check_and_apply_block(redis: Redis, current_user: str, increment: bool = True) -> tuple[Response, int] | None:
    block_key = f"blocked:{current_user}"
    count_key = f"count429:{current_user}"

    ttl = redis.ttl(block_key)
    if ttl > 0:
        minutes = max(1, math.ceil(ttl / 60))
        return create_error_response(f"You have been temporarily blocked due to repeated rate limit violations. Please try again in {minutes} minute(s).", 403)

    if not increment:
        return None

    pipe = redis.pipeline()
    pipe.incr(count_key)
    pipe.expire(count_key, VIOLATION_WINDOW_TTL)

    count, _ = pipe.execute()

    if count == 3:
        return create_error_response("You are approaching the rate limit. One more failed attempt will block you for 30 minutes. Please try again later.", 429)

    if count >= 4:
        redis.set(block_key, 1, ex=BLOCK_TTL)
        redis.delete(count_key)

        return create_error_response("You have been temporarily blocked due to repeated rate limit violations.", 403)

    return None