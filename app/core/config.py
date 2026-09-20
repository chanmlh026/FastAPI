from typing import Optional

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Environment(BaseModel):
    database_url: str = Field(min_length=1)
    pagination_token_key: str | None = Field(default=None, repr=False)


saved_environment: Optional[Environment] = None


def get_environment() -> Environment:
    global saved_environment

    if saved_environment is None:
        load_dotenv()
        saved_environment = Environment(
            database_url=os.environ["DATABASE_URL"],
            pagination_token_key=os.environ.get("PAGINATION_TOKEN_KEY"),
        )

    return saved_environment
