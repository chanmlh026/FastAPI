from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BeforeValidator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.customers.models import CustomerModel
from app.customers.pagination import decode_cursor, encode_cursor, token_cipher
from app.customers.schemas import (
    CustomerCreate,
    CustomerID,
    CustomerNameField,
    CustomerResponse,
    ListCustomersResponse,
)
from app.db.database import get_db

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def validate_page_size(value: str | int) -> int:
    try:
        size = int(value)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "page_size must be a nonnegative integer"
        ) from None
    if size < 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "page_size must be a nonnegative integer"
        )
    return min(size or 50, 1000)


def get_customer_or_404(customer_id: int, db: Session) -> CustomerModel:
    customer = db.get(CustomerModel, customer_id)

    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    return customer


@router.get("", response_model=ListCustomersResponse)
def list_customers(
    db: DatabaseSession,
    q: Annotated[
        str, Query(description="Case-insensitive name substring; blank lists all.")
    ] = "",
    page_size: Annotated[
        int,
        BeforeValidator(validate_page_size),
        Query(description="Maximum results: default 50 (also for 0), capped at 1000."),
    ] = 50,
    page_token: Annotated[
        str, Query(description="Opaque continuation token; keep q unchanged.")
    ] = "",
):
    """List customers by ascending ID. Invalid pagination arguments return 400."""
    size = page_size
    query = q.strip()
    token_cipher()
    statement = select(CustomerModel).order_by(CustomerModel.customer_id)
    if query:
        statement = statement.where(
            CustomerModel.name.icontains(query, autoescape=True)
        )
    if page_token:
        last_id = decode_cursor(page_token, query)
        statement = statement.where(CustomerModel.customer_id > last_id)
    rows = list(db.scalars(statement.limit(size + 1)))
    customers = rows[:size]
    next_token = (
        encode_cursor(customers[-1].customer_id, query) if len(rows) > size else ""
    )
    return {"customers": customers, "next_page_token": next_token}


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: CustomerID, db: DatabaseSession):
    """
    Get a customer.
    """
    database_customer = get_customer_or_404(customer_id, db)

    return database_customer


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer: CustomerCreate, db: DatabaseSession):
    """
    Create a new customer.
    """
    database_customer = CustomerModel(**customer.model_dump())

    db.add(database_customer)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(status.HTTP_409_CONFLICT, "Customer ID already exists")

    db.refresh(database_customer)

    return database_customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: CustomerID, customer: CustomerNameField, db: DatabaseSession
):
    """
    Update part of a customer.
    """
    database_customer = get_customer_or_404(customer_id, db)

    database_customer.name = customer.name

    db.commit()
    db.refresh(database_customer)

    return database_customer


@router.delete("/{customer_id}")
def delete_customer(customer_id: CustomerID, db: DatabaseSession):
    """
    Delete a customer.
    """
    database_customer = get_customer_or_404(customer_id, db)

    db.delete(database_customer)
    db.commit()

    return {"message": "Customer deleted"}
