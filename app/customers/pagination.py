"""Opaque, authenticated cursors for the customers collection."""

import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import get_environment


def token_cipher() -> Fernet:
    key = get_environment().pagination_token_key
    if not key:
        raise HTTPException(503, "Pagination token key is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except ValueError, UnicodeError:
        raise HTTPException(503, "Pagination token key is invalid") from None


def encode_cursor(cipher: Fernet, customer_id: int, query: str) -> str:
    payload = {"version": 1, "last_id": customer_id, "q": query}
    return cipher.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")


def decode_cursor(cipher: Fernet, token: str, query: str) -> int:
    try:
        payload = json.loads(cipher.decrypt(token.encode("ascii")))
        if (
            not isinstance(payload, dict)
            or type(payload.get("version")) is not int
            or payload["version"] != 1
            or type(payload.get("last_id")) is not int
            or not 1 <= payload["last_id"] <= 2**31 - 1
            or payload.get("q") != query
        ):
            raise ValueError
        return payload["last_id"]
    except InvalidToken, ValueError, UnicodeError, TypeError:
        raise HTTPException(
            400, "Invalid page_token or search does not match"
        ) from None
