from fastapi import FastAPI

from app.customers.router import router as customer_router

app = FastAPI()

app.include_router(customer_router)
