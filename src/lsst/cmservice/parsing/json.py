import json


def coerce_json_value(v: str) -> object:
    """For a given string value, return it as a JSON-coerced object"""
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        # Especially with strings, `json.loads("hello")` is an error
        return v
