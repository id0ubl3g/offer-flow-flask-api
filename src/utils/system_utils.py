from email_validator import validate_email, EmailNotValidError
from flask_limiter.util import get_remote_address
from flask import g
import re

def is_valid_email(email: str) -> bool:
    try:
        validate_email(email)
        return True
    
    except EmailNotValidError:
        return False

def user_or_ip():
    if hasattr(g, "user") and g.user:
        return str(g.user["id"])
    
    return get_remote_address()

def validate_user_data(data: dict) -> str | None:
    validators = {
        "name": [
            (r'^.{2,100}$', "Name must be between 2 and 100 characters.")
        ],
        "password": [
            (r'^.{8,64}$', "Password must be at least 8 characters and max 64."),
            (r'(?=.*[a-z])', "Password must contain at least one lowercase letter."),
            (r'(?=.*[A-Z])', "Password must contain at least one uppercase letter."),
            (r'(?=.*\d)', "Password must contain at least one digit."),
            (r'(?=.*[\W_])', "Password must contain at least one special character.")
        ],
        "code": [
            (r'^[A-Za-z0-9]{6}$', "Code must be exactly 6 alphanumeric characters.")
        ]
    }

    for field, rules in validators.items():
        value = data.get(field)

        if value is None:
            continue

        value = str(value).strip()

        if value == "":
            continue

        for pattern, error_msg in rules:
            if not re.match(pattern, value):
                return error_msg

    return None