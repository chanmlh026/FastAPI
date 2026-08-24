from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

customers = {
    101: "Tim"
    102: "Roy"
}

class Customer(BaseModel):
    user_id: int
    name: str

class CustomerUpdate(BaseModel):
    name: str

@app.get("/customers/{user_id}")







