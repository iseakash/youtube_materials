# Password Login API with Brute-Force Protection

A secure FastAPI-based login API for a learning portal with brute-force protection via IP-based rate limiting.

## Features

- Rate limiting: 5 login attempts per minute per IP (via slowapi)
- Generic error messages (never reveals whether email or password was wrong)
- Pydantic `SecretStr` for password — automatically redacted in logs
- Cryptographically secure token on successful login (`secrets.token_urlsafe`)
- Token not printed in server logs
- Proper HTTP status codes (200, 401, 429)

## Architecture

### Request Flow

```
Client                          Server
  │                               │
  │  POST /login                  │
  │  {email, password}            │
  │ ──────────────────────────►   │
  │                               ├─ Rate limit check (slowapi: 5/min per IP)
  │                               │   └─ Exceeded? → 429 Too Many Requests
  │                               ├─ Validate: EmailStr + SecretStr
  │                               ├─ Credential check (generic message)
  │                               │   └─ Wrong? → 401 "Invalid email or password"
  │                               ├─ Generate token (secrets.token_urlsafe)
  │                               ├─ Store token in active_tokens dict
  │  ◄──────────────────────────  │
  │  200 {"message", "token"}     │
```

### Server-Side Data

| Data | Source | Description |
|------|--------|-------------|
| Admin email | Hardcoded constant | `admin@example.com` |
| Admin password | `os.getenv("ADMIN_PASSWORD")` | Loaded from `.env`, never hardcoded |
| Active tokens | `active_tokens` dict | In-memory: `token → email` mapping |

## Design Decisions

| Requirement | Implementation | Reasoning |
|---|---|---|
| 5 attempts/min per IP | `@limiter.limit("5/minute")` with `get_remote_address` | Blocks brute-force attacks per IP without affecting other users |
| Generic error message | Always `"Invalid email or password"` | Attacker cannot distinguish valid emails from invalid ones |
| 401 for bad creds | `HTTPException(status_code=401, ...)` | Standard HTTP status for authentication failure |
| 429 on rate limit | slowapi auto-returns 429 via `RateLimitExceeded` handler | Standard HTTP status for rate limiting |
| Simple token | `secrets.token_urlsafe(32)` | Cryptographically secure, no external dependencies |
| Password not in logs | Pydantic `SecretStr` on password field | `SecretStr` auto-redacts the value in all repr/str calls |
| Token not in logs | No application code logs the token; uvicorn access logs only log method, path, status, time | Response body is never part of default access logs |
| No hardcoded secrets | Password read from `os.getenv("ADMIN_PASSWORD")` via `.env` | Keeps secrets out of source code |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Set the admin password

A `.env` file is provided with a default password. Change it for production:

```
ADMIN_PASSWORD=secret123
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# Successful login
curl -X POST "http://127.0.0.1:8000/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "secret123"}'

# Failed login
curl -X POST "http://127.0.0.1:8000/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "wrongpass"}'

# Rate limit — send 6+ requests in quick succession to get 429
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/login` | None (rate-limited by IP) | Login with email and password |
| GET | `/health` | None | Health check |

## Why Login is Unauthenticated (No `Security` Dependency)

The `/login` endpoint intentionally does **not** require an API key or any prior authentication via the `Security` dependency.

**Reason:** Login is the entry point — a user hits this endpoint to *obtain* credentials (a token). If it required an API key, we'd have a circular dependency: *"You need a key to get a key."* Instead, brute-force protection is handled entirely by slowapi's IP-based rate limiting (`@limiter.limit("5/minute")`).

## Why the Function Signature Uses Two Parameters

The endpoint uses `def login(request: Request, creds: LoginRequest)` instead of `def login(creds: LoginRequest)`.

**Reason:** The `@limiter.limit("5/minute")` decorator internally needs the FastAPI `Request` object to extract the client's IP address (via `get_remote_address()`). It injects this as the **first positional argument automatically**.

```python
# ❌ Won't work — slowapi passes a Request object,
#    but the parameter expects LoginRequest
@limiter.limit("5/minute")
def login(creds: LoginRequest):
    ...

# ✅ Works — slowapi passes Request as first arg,
#    Pydantic body comes as second arg
@limiter.limit("5/minute")
def login(request: Request, creds: LoginRequest):
    ...
```

You **cannot** name the Pydantic body parameter `request` either, because Python doesn't allow duplicate parameter names in the same function signature.

## ⚠️ Important Security Pointer: Password and Token Must Not Be Logged

### Why this matters

If passwords or tokens appear in server logs (files, stdout, cloud logging services), any attacker who gains read access to those logs can:
- Extract user passwords
- Steal active session tokens and impersonate users

This is a common vulnerability because developers often log request bodies for debugging without sanitizing sensitive fields.

### How we prevent it

#### 1. `SecretStr` — Password auto-redaction

Pydantic's `SecretStr` is a special type that stores the actual value internally but **always displays `'**********'` when converted to string**.

```python
from pydantic.types import SecretStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr   # ✅ Logged as '**********'

# Example behavior:
req = LoginRequest(email="admin@example.com", password="mySecret123")
print(str(req))
# Output: email='admin@example.com' password=SecretStr('**********')

# To get the actual value, you must explicitly call:
actual = req.password.get_secret_value()  # "mySecret123"
```

This means if any logging framework, error handler, or debugging tool accidentally calls `str()` or `repr()` on the request object, the password is automatically masked.

#### 2. `secrets.token_urlsafe(32)` — Secure token generation

```python
import secrets

token = secrets.token_urlsafe(32)
# Example output: "xK8mZq2pR5vL9nA3cF7jW1bY4eD6gH0iJ2kM4oP6rS"
```

- Uses the `secrets` module (Python's standard library for cryptographically secure random values)
- `32` = 32 random bytes → base64url-encoded → 43-character URL-safe string
- `token_urlsafe` produces only alphanumeric characters + `-` and `_` (no URL encoding needed)
- The token is generated on the server and never sent to the client in logs
- The application never logs the token value

#### 3. Uvicorn access logs

By default, Uvicorn's access logs only record:
- HTTP method (`POST`)
- Path (`/login`)
- Status code (`200`, `401`, `429`)
- Response time

The **request body and response body are never included** in default access logs, so passwords and tokens are never leaked through this channel.

### Summary

| Technique | What it protects | How |
|-----------|-----------------|-----|
| `SecretStr` | Password | Auto-redacts in all string representations |
| No token logging | Token | Application code never logs the token |
| Uvicorn access logs | Both | Default format excludes request/response bodies |
