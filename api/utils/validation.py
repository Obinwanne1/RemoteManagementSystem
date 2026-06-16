"""Request body validation decorator using marshmallow."""
from functools import wraps
from flask import request, jsonify


def validate_body(schema_class):
    """Validate JSON request body against a marshmallow schema.
    Returns 400 with field-level errors on validation failure."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            errors = schema_class().validate(data)
            if errors:
                return jsonify({"error": "Validation failed", "details": errors}), 400
            return fn(*args, **kwargs)
        return wrapper
    return decorator
