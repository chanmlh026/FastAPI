from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.customers.router import router as customer_router

app = FastAPI()

app.include_router(customer_router)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.rstrip("/") == "/auth/register":
        # Validation errors normally echo input, including rejected passwords.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: error[key] for key in ("type", "loc", "msg")}
                    for error in exc.errors()
                ]
            },
        )
    return await request_validation_exception_handler(request, exc)
