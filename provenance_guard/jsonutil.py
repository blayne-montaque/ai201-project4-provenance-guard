"""Reject nonstandard JSON constants and ambiguous duplicate object keys."""
import json


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON value")


def strict_loads(value):
    return json.loads(value, object_pairs_hook=_pairs, parse_constant=_reject_constant)

