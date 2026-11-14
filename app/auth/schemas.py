from typing import Annotated
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
)

from app.auth.constants import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
)

EmailStrProcessed = Annotated[
    EmailStr,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=MAX_EMAIL_LENGTH
    ),
]


class UserCreate(BaseModel):
    email: EmailStrProcessed = Field(
        description=(
            "Unicode email address normalised by email-validator; surrounding "
            "whitespace is removed and the entire address is lowercased."
        ),
    )
    password: SecretStr = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="15–128 characters, including spaces and Unicode; never trimmed.",
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
