import base64
import json
import re

from flask import request
from pydantic import BaseModel, ConfigDict

from ..errors import ApiError


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def body(model):
    """
    Parses and validates the JSON body. Unknown fields are rejected (no mass assignment).
    """
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError(400, "bad_request", "Expected a JSON body.")
    return model.model_validate(data)


def args(model):
    data = {k: v for k, v in request.args.items() if v != ""}
    return model.model_validate(data)


def encode_cursor(sort_value, row_id):
    raw = json.dumps([sort_value, row_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor):
    if not cursor:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value, row_id = json.loads(base64.urlsafe_b64decode(padded))
        return str(value), int(row_id)
    except (ValueError, TypeError):
        raise ApiError(400, "bad_cursor", "Invalid pagination cursor.")


def fulltext_query(q):
    """
    Turns free text into a safe InnoDB boolean-mode query: every word required,
    prefix-matched. Operators typed by the user are stripped.
    """
    words = re.findall(r"[\w']{2,}", q or "")[:8]
    return " ".join(f"+{w}*" for w in words) or None


def page(items, limit, sort_key="sort_value"):
    has_more = len(items) > limit
    items = items[:limit]
    cursor = encode_cursor(items[-1][sort_key], items[-1]["id"]) if has_more and items else None
    for item in items:
        item.pop("id", None)
        item.pop(sort_key, None)
    return {"items": items, "next_cursor": cursor}
