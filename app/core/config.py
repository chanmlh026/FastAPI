from typing import Optional
from base64 import urlsafe_b64decode
from binascii import Error as Base64Error
from datetime import UTC, datetime, timedelta

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
MIN_JWT_KEY_BYTES = 32


class JWTConfigurationError(Exception):
    """JWT settings cannot safely be used; never include their values in errors."""


class Environment(BaseModel):
    database_url: str = Field(min_length=1)
    pagination_token_key: str | None = Field(default=None, repr=False)
    jwt_secret_key: SecretStr | None = Field(default=None, repr=False)
    access_token_expire_minutes: str | int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES


saved_environment: Optional[Environment] = None


def get_environment() -> Environment:
    global saved_environment

    if saved_environment is None:
        load_dotenv()
        saved_environment = Environment(
            database_url=os.environ.get("DATABASE_URL"),
            pagination_token_key=os.environ.get("PAGINATION_TOKEN_KEY"),
            jwt_secret_key=os.environ.get("JWT_SECRET_KEY"),
            access_token_expire_minutes=os.environ.get(
                "ACCESS_TOKEN_EXPIRE_MINUTES", str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)
            ),
        )

    return saved_environment


def get_jwt_configuration() -> tuple[bytes, timedelta]:
    """Validate lazily so JWT misconfiguration does not disable unrelated routes."""
    environment = get_environment()
    raw_key = (
        environment.jwt_secret_key.get_secret_value()
        if environment.jwt_secret_key is not None
        else ""
    )
    try:
        key = bytes.fromhex(raw_key)
        minutes = int(environment.access_token_expire_minutes)
        lifetime = timedelta(minutes=minutes)
    except ValueError, OverflowError:
        raise JWTConfigurationError() from None
    try:
        pagination_key = (
            urlsafe_b64decode(environment.pagination_token_key)
            if environment.pagination_token_key
            else None
        )
    except ValueError, Base64Error:
        # Invalid pagination configuration must not independently disable login.
        pagination_key = None
    if (
        key.hex() != raw_key.lower()
        or len(key) < MIN_JWT_KEY_BYTES
        or len(set(key)) <= 1  # Reject obvious repeated-byte placeholders.
        or raw_key == environment.pagination_token_key
        or key == pagination_key
        or minutes <= 0
        or lifetime > datetime.max.replace(tzinfo=UTC) - datetime.now(UTC)
    ):
        raise JWTConfigurationError()
    return key, lifetime
