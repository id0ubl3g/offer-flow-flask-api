from email_validator import validate_email, EmailNotValidError
import re

def is_valid_email(email: str) -> bool:
    try:
        validate_email(email)
        return True
    
    except EmailNotValidError:
        return False

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