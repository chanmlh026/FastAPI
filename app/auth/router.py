from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.auth.service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    login_user,
    register_user,
)
from app.core.config import JWTConfigurationError
from app.db.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": "Email already registered"}},
)
def register(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    """Create an account. Email uniqueness is case-insensitive. No login token is issued."""
    try:
        return register_user(db, user)
    except EmailAlreadyRegistered:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Email already registered"
        ) from None


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Authentication unavailable"
        },
    },
)
def login(
    credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
):
    """Authenticate an active user and issue an HS256 access token. No customer protection yet."""
    try:
        token = login_user(db, credentials)
    except InvalidCredentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTConfigurationError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication unavailable"
        ) from None
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return token
