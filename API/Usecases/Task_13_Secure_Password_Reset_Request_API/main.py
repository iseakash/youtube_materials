from fastapi import FastAPI, HTTPException, Request  # web framework, error handling, request object for slowapi
import secrets                                        # cryptographically secure random token generation
import time                                           # unix timestamps for token expiry check
from dotenv import load_dotenv                        # load .env file into os.environ (not strictly needed here, kept for consistency)
from pathlib import Path                              # build absolute path to .env
from slowapi import Limiter                           # rate limiter – prevents email enumeration via brute force
from slowapi.errors import RateLimitExceeded          # exception raised when rate limit hit
from slowapi.util import get_remote_address           # extracts client IP for rate limiting
from slowapi import _rate_limit_exceeded_handler      # built-in JSON handler for 429 responses
from pydantic import BaseModel, EmailStr, Field       # schema validation, email type, field constraints

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Secure Password Reset Request API")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Pre-registered users — in production these would be in a database.
# Passwords are plain-text here for demo; real apps use hashing (bcrypt, argon2).
users = {
    "alice@example.com": {"password": "AlicePass123", "name": "Alice"},
    "bob@example.com":   {"password": "BobPass456",   "name": "Bob"},
}

# Active reset tokens: token → {email, created_at}
# Tokens expire after 15 minutes and are deleted after one use.
reset_tokens: dict[str, dict] = {}

TOKEN_TTL = 900  # 15 minutes in seconds


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.post("/password-reset/request")
@limiter.limit("3/hour")
def reset_request(request: Request, body: ResetRequest):
    """Returns the same message whether or not the email exists — attackers cannot tell which."""

    user = users.get(body.email)
    if user:
        token = secrets.token_urlsafe(32)
        reset_tokens[token] = {
            "email": body.email,
            "created_at": time.time(),
        }

    return {
        "message": "If the email is registered, a reset link has been sent",
        # "debug_token": token,        # ← only for testing; remove in production
    }


@app.post("/password-reset/confirm")
def reset_confirm(body: ResetConfirm):
    """Validates token, checks expiry (15 min), updates password, and deletes token (one-time use)."""

    token_data = reset_tokens.get(body.token)
    if token_data is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token"
        )

    if time.time() - token_data["created_at"] > TOKEN_TTL:
        reset_tokens.pop(body.token, None)
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token"
        )

    email = token_data["email"]
    users[email]["password"] = body.new_password

    reset_tokens.pop(body.token, None)

    return {"message": "Password reset successful"}
