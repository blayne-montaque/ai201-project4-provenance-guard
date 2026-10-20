import re

from flask import request

from .errors import APIError
from .jsonutil import strict_loads


def json_object():
    if not request.is_json:
        raise APIError("invalid_json", "Use a JSON object with Content-Type application/json.")
    try:
        value = strict_loads(request.get_data())
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise APIError("invalid_json", "The request must contain valid, unambiguous JSON.") from None
    if type(value) is not dict:
        raise APIError("invalid_json", "The request must contain a JSON object.")
    return value


def fields(value, required, optional=()):
    if not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise APIError("invalid_fields", "Required fields are missing or unknown fields were supplied.")


def string(value, key, maximum):
    result = value.get(key)
    if not isinstance(result, str) or not 1 <= len(result.strip()) <= maximum:
        raise APIError("invalid_field", f"{key} must be a nonempty string of at most {maximum} characters.")
    return result.strip()


def creator(value):
    result = string(value, "creator_id", 80)
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", result):
        raise APIError("invalid_creator_id", "creator_id contains unsupported characters.")
    return result

