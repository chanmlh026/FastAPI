from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import UserCreate, UserResponse
from app.auth.service import EmailAlreadyRegistered, register_user
from app.db.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already registered"}},
)
def register(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    """Create an account. Email uniqueness is case-insensitive. No login token is issued."""
    try:
        return register_user(db, user)
    except EmailAlreadyRegistered:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Email already registered"
        ) from None
