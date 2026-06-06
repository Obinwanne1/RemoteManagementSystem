"""Password strength validation utility."""
import re


def validate_password(password: str) -> list:
    """Return list of error strings. Empty list = valid."""
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("at least one number")
    if not re.search(r'[!@#$%^&*()\[\],.?":{}|<>_\-+=~`\\/]', password):
        errors.append("at least one special character (!@#$% etc.)")
    return errors


def password_error_response(password: str):
    """Return (errors_list, http_400_message) or ([], None) if valid."""
    errors = validate_password(password)
    if errors:
        msg = "Password must include: " + ", ".join(errors)
        return errors, msg
    return [], None
