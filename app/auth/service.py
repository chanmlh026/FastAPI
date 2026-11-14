from secrets import token_urlsafe

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.constants import EMAIL_UNIQUE_INDEX
from app.auth.models import UserModel
from app.auth.passwords import hash_password, verify_password
from app.auth.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.auth.tokens import create_access_token
from app.core.config import get_jwt_configuration

# Generated once per worker with the same Argon2id profile as registered users.
_DUMMY_PASSWORD_HASH = hash_password(token_urlsafe())


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def login_user(db: Session, credentials: UserLogin) -> TokenResponse:
    key, lifetime = get_jwt_configuration()
    user = db.scalar(select(UserModel).where(UserModel.email == str(credentials.email)))
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    verified = verify_password(credentials.password.get_secret_value(), password_hash)
    if user is None or not verified or not user.is_active:
        raise InvalidCredentials()
    return TokenResponse(access_token=create_access_token(user.id, key, lifetime))


def register_user(db: Session, user: UserCreate) -> UserResponse:
    """Own the registration transaction; roll back every failed database write."""
    database_user = UserModel(
        email=str(user.email),
        password_hash=hash_password(user.password.get_secret_value()),
    )
    try:
        db.add(database_user)
        db.flush()
        response = UserResponse.model_validate(database_user)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        if (
            isinstance(exc, IntegrityError)
            and isinstance(exc.orig, UniqueViolation)
            and exc.orig.diag.constraint_name == EMAIL_UNIQUE_INDEX
        ):
            raise EmailAlreadyRegistered() from None
        raise
    return response
