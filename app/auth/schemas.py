from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.auth.constants import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
)


class UserCreate(BaseModel):
    email: EmailStr = Field(
        max_length=MAX_EMAIL_LENGTH,
        description="ASCII email address; surrounding whitespace is removed and case ignored.",
    )
    password: SecretStr = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="15–128 characters, including spaces and Unicode; never trimmed.",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value.isascii():
                raise ValueError("Use an ASCII email address")
            return value.lower()
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
