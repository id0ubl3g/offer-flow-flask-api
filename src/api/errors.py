from src.extensions import get_redis
from src.services.rate_limit_service import check_and_apply_block
from src.utils.system_utils import user_or_ip
from src.utils.return_responses import create_error_response

from flask import Flask, Response

def register_error_handlers(app: Flask) -> None:
    @app.before_request
    def enforce_block() -> tuple[Response, int] | None:
        return check_and_apply_block(get_redis(), user_or_ip(), increment=False)

    @app.errorhandler(429)
    def ratelimit_error(e) -> tuple[Response, int]:
        response = check_and_apply_block(get_redis(), user_or_ip())

        if response:
            return response

        return create_error_response("Too many requests. Please try again later.", 429)