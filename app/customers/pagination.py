"""Opaque, authenticated cursors for the customers collection."""

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_environment
from app.customers.schemas import CustomerIDValue


class CursorPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    version: int = Field(ge=1, le=1)
    last_id: CustomerIDValue
    q: str


saved_token_cipher: Fernet | None = None


def token_cipher() -> Fernet:
    global saved_token_cipher

    if saved_token_cipher is not None:
        return saved_token_cipher

    key = get_environment().pagination_token_key
    if not key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Pagination token key is not configured",
        )
    try:
        saved_token_cipher = Fernet(key.encode("ascii"))
    except ValueError, UnicodeError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Pagination token key is invalid"
        ) from None

    return saved_token_cipher


def encode_cursor(customer_id: int, query: str) -> str:
    payload = CursorPayload(version=1, last_id=customer_id, q=query)
    return (
        token_cipher()
        .encrypt(payload.model_dump_json().encode("utf-8"))
        .decode("ascii")
    )


def decode_cursor(token: str, query: str) -> int:
    try:
        payload = CursorPayload.model_validate_json(
            token_cipher().decrypt(token.encode("ascii"))
        )
        if payload.q != query:
            raise ValueError
        return payload.last_id
    except InvalidToken, ValueError, UnicodeError, TypeError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid page_token or search does not match"
        ) from None
