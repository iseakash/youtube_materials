from fastapi import FastAPI, HTTPException, Request
import os
import secrets
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel, EmailStr
from pydantic.types import SecretStr

load_dotenv()

app = FastAPI(title="Password Login API with Brute-Force Protection")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

active_tokens = {}


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


@app.post("/login")
@limiter.limit("5/minute")
def login(request: Request, creds: LoginRequest):
    if (
        creds.email != ADMIN_EMAIL
        or creds.password.get_secret_value() != ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = secrets.token_urlsafe(32)
    active_tokens[token] = creds.email

    return {
        "message": "Login successful",
        "token": token
    }


@app.get("/health")
def health_check():
    return {
        "status": "running",
        "message": "API is running"
    }
