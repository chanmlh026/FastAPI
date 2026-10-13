from typing import Annotated
from fastapi import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.customers.constants import MAX_NAME_LENGTH


class CustomerNameField(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not value:
            raise ValueError("Name cannot be blank")

        return value


CustomerIDValue = Annotated[int, Field(ge=1, le=2**31 - 1)]
CustomerID = Annotated[int, Path(ge=1, le=2**31 - 1)]


class CustomerCreate(CustomerNameField):
    customer_id: CustomerIDValue


class CustomerResponse(CustomerNameField):
    model_config = ConfigDict(from_attributes=True)

    customer_id: int


class ListCustomersResponse(BaseModel):
    customers: list[CustomerResponse]
    next_page_token: str = ""
