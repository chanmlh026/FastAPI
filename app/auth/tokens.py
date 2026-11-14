from datetime import UTC, datetime, timedelta

import jwt

from app.auth.constants import JWT_ALGORITHM
from app.core.config import JWTConfigurationError


def create_access_token(user_id: int, key: bytes, lifetime: timedelta) -> str:
    issued_at = datetime.now(UTC)
    try:
        expires_at = issued_at + lifetime
    except OverflowError:
        raise JWTConfigurationError() from None
    return jwt.encode(
        {"sub": str(user_id), "iat": issued_at, "exp": expires_at},
        key,
        algorithm=JWT_ALGORITHM,
    )
