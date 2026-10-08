from flask import jsonify, Response

def create_success_return_response(message: str = None, data: str = None) -> dict:
    response = {
        'message': message,
        'data': data
    }
    return response

def create_error_response(message: str, code: int) -> tuple[Response, int]:
    return jsonify({'error': message}), code