from fastapi import FastAPI, HTTPException, Security, Request  # web framework, error handling, Security DI, request object
import os                                           # read env vars from OS / .env
from pathlib import Path                            # build absolute path to .env
import time                                         # unix timestamps for rolling-window rate limiting
from dotenv import load_dotenv                      # load .env file into os.environ
from fastapi.security import APIKeyHeader           # extract API key from HTTP header

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="API Usage Plan and Subscription Limiting API")

# API_KEYS maps each key to its plan name and per-minute request limit.
# Keys are loaded from .env — never hard-coded.
API_KEYS = {
    os.getenv("FREE_KEY"):       {"plan": "free",       "limit": 5},
    os.getenv("PRO_KEY"):        {"plan": "pro",        "limit": 20},
    os.getenv("ENTERPRISE_KEY"): {"plan": "enterprise", "limit": 100},
}

# Per-key rate tracker: api_key → list of Unix timestamps of recent requests.
# The Security() guard reads, filters, and appends to this dict.
rate_tracker: dict[str, list[float]] = {}  # e.g. {"free-key-001": [1721812345.67, 1721812350.12]}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")


def verify_and_throttle(key: str = Security(api_key_header)):
    """Authenticates the API key, enforces per-plan rate limit, and returns plan info + remaining."""

    if key not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    plan_info = API_KEYS[key]
    now = time.time()
    window = 60

    timestamps = [t for t in rate_tracker.get(key, []) if now - t < window]  # keep only requests within the last 60 seconds

    if len(timestamps) >= plan_info["limit"]:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for your plan"
        )

    timestamps.append(now)
    rate_tracker[key] = timestamps

    return {
        "plan": plan_info["plan"],
        "remaining": plan_info["limit"] - len(timestamps),
    }


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.get("/data")
def get_data(usage: dict = Security(verify_and_throttle)):  # Security() returns {plan, remaining} dict, not just a key
    """Returns sample data along with the user's current plan and remaining request count."""

    return {
        "data": [
            {"id": 1, "name": "Analytics Report Q1"},
            {"id": 2, "name": "User Activity Log"},
            {"id": 3, "name": "Revenue Summary"},
        ],
        "plan": usage["plan"],
        "requests_remaining": usage["remaining"],
    }
