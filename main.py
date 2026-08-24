from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Temperary customer data
customers = {
    101: "John",
    102: "Mary",
    103: "David"
}

# The structure of a complete customer
class Customer(BaseModel):
    user_id: int
    name: str

# The fields that can be udpated
class CustomerUpdate(BaseModel):
    name: str

# Get a customer
@app.get("/customers/{user_id}")
def get_customer(user_id: int):
    return {
        "user_id": user_id,
        "name": customers[user_id]
    }

# Create a new customer
@app.post("/customers")
def create_customer(customer: Customer):
    customers[customer.user_id] = customer.name

    return customer

# Update part of a customer
@app.patch("/customers/{user_id}")
def update_customer(user_id: int, customer: CustomerUpdate):
    customers[user_id] = customer.name

    return customer

# @app.put("/customers/{user_id}")
# def replace_customer(user_id: int, customer: Customer):
#     customers[user_id] = customer.name

#     return customer

# Delete a customer
@app.delete("/customers/{user_id}")
def delete_customer(user_id: int):
    del customers[user_id]

    return {
        "message": "Customer deleted"
    }
