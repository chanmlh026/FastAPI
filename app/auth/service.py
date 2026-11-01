from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.constants import EMAIL_UNIQUE_INDEX
from app.auth.models import UserModel
from app.auth.passwords import hash_password
from app.auth.schemas import UserCreate, UserResponse


class EmailAlreadyRegistered(Exception):
    pass


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
