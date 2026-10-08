from flask import jsonify, Response, current_app

def create_success_return_response(message: str = None, data: str = None) -> dict:
    response = {
        'message': message,
        'data': data
    }
    return response

def create_error_response(message: str, code: int) -> tuple[Response, int]:
    return jsonify({'error': message}), code

def create_internal_error_response() -> tuple[Response, int]:
    current_app.logger.exception("Unhandled error while processing the request")
    return create_error_response("An error occurred while processing the request", 500)