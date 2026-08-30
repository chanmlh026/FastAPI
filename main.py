from fastapi import FastAPI, HTTPException, status, Path
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

app = FastAPI()

# Temperary customer data
customers = {
    101: "John",
    102: "Mary",
    103: "David"
}

# The structure of a complete customer
class Customer(BaseModel):
    customer_id: int = Field(ge=1, le=2**31-1)
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not value:
            raise ValueError("Name cannot be blank")

        return value


# The fields that can be udpated
class CustomerUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not value:
            raise ValueError("Name cannot be blank")

        return value

CustomerID = Annotated[int, Path(ge=1, le=2**31-1)]

# Get a customer
@app.get("/customers/{customer_id}")
def get_customer(customer_id: CustomerID):

    if customer_id not in customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    return {
        "customer_id": customer_id,
        "name": customers[customer_id]
    }

# Create a new customer
@app.post("/customers")
def create_customer(customer: Customer):

    if customer.customer_id in customers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer ID already exists"
        )
    
    customers[customer.customer_id] = customer.name

    return customer

# Update part of a customer
@app.patch("/customers/{customer_id}")
def update_customer(customer_id: CustomerID, customer: CustomerUpdate):

    if customer_id not in customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    customers[customer_id] = customer.name

    return customer

# @app.put("/customers/{customer_id}")
# def replace_customer(customer_id: int, customer: Customer):
#     customers[customer_id] = customer.name

#     return customer

# Delete a customer
@app.delete("/customers/{customer_id}")
def delete_customer(customer_id: CustomerID):

    if customer_id not in customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    del customers[customer_id]

    return {
        "message": "Customer deleted"
    }
