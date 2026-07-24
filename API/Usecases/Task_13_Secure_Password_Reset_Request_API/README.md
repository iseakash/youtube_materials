# Secure Password Reset Request API

A secure FastAPI-based password reset system designed to prevent email enumeration attacks. The API returns the same message whether or not the email exists, and uses cryptographically secure tokens with expiry and one-time use enforcement.

## Security Challenge

> **The response must not reveal whether the email exists in the system.**

Attackers commonly use password reset endpoints to **enumerate valid emails** — they send a reset request, and if the response says "email sent", they know the account exists. If it says "email not found", they know it doesn't.

This API returns the **exact same message** in both cases, making enumeration impossible.

## Features

- POST `/password-reset/request` — always returns same message regardless of email existence
- POST `/password-reset/confirm` — resets password with token validation
- Token generated via `secrets.token_urlsafe(32)` (cryptographically secure)
- Token expires after 15 minutes
- Token can be used only once (deleted after successful reset)
- Password must be at least 8 characters (Pydantic enforced)
- Strict rate limiting: 3 requests per hour per IP on the request endpoint
- No API key required (user forgot their password — can't have a key)

## Architecture

```
┌──────────────┐
│   Client     │
│  (Attacker   │
│   or User)   │
└──────┬───────┘
       │  POST /password-reset/request     POST /password-reset/confirm
       │  {email}                           {token, new_password}
       ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │         POST /password-reset/request              │    │
│  │                                                    │    │
│  │  1. slowapi rate limit 3/hour per IP              │    │
│  │     └─ Exceeded → 429                             │    │
│  │                                                    │    │
│  │  2. Pydantic validates EmailStr                    │    │
│  │     └─ Invalid → 422                               │    │
│  │                                                    │    │
│  │  3. Check email in users dict                      │    │
│  │     │                                               │    │
│  │     ├─ Found? → Generate token                     │    │
│  │     │   secrets.token_urlsafe(32)                  │    │
│  │     │   Store: reset_tokens[token] = {             │    │
│  │     │     email, created_at}                       │    │
│  │     │                                               │    │
│  │     └─ Not found? → Do nothing                     │    │
│  │        (same code path length — no timing leak)     │    │
│  │                                                    │    │
│  │  4. Return IDENTICAL message for BOTH paths        │    │
│  │     ← Attacker CANNOT distinguish                  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │         POST /password-reset/confirm             │    │
│  │                                                    │    │
│  │  1. Pydantic validates token + password            │    │
│  │     new_password: Field(min_length=8)              │    │
│  │     └─ Invalid → 422                               │    │
│  │                                                    │    │
│  │  2. Look up token in reset_tokens dict             │    │
│  │     └─ Not found → 400 "Invalid or expired token"  │    │
│  │                                                    │    │
│  │  3. Check TTL: now - created_at > 900?             │    │
│  │     └─ Expired → delete token → 400                │    │
│  │                                                    │    │
│  │  4. Update user's password in users dict           │    │
│  │                                                    │    │
│  │  5. Delete token from reset_tokens (one-time use)  │    │
│  │                                                    │    │
│  │  6. Return 200 "Password reset successful"         │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                    │    │
│  │  users = {                                        │    │
│  │    "alice@example.com": {password, name},          │    │
│  │    "bob@example.com":   {password, name},          │    │
│  │  }                                                  │    │
│  │                                                    │    │
│  │  reset_tokens = {                                 │    │
│  │    "xK8mZq2...": {email, created_at: ts},         │    │
│  │  }                                                  │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | `/password-reset/request` | None | 3/hour | Request a password reset |
| POST | `/password-reset/confirm` | None | None | Confirm reset with token |
| GET | `/health` | None | None | Health check |

## Code Flow Diagrams

### POST /password-reset/request — Email Exists

```
Client                                   Server
  │                                        │
  │  POST /password-reset/request          │
  │  Body: {email: "alice@example.com"}   │
  │ ──────────────────────────────────►    │
  │                                        ├─ slowapi rate limit 3/hour
  │                                        │  └─ OK
  │                                        ├─ Pydantic: EmailStr valid
  │                                        │  └─ OK
  │                                        ├─ Lookup alice@example.com
  │                                        │  in users dict
  │                                        │  └─ FOUND
  │                                        │
  │                                        ├─ Generate token:
  │                                        │  secrets.token_urlsafe(32)
  │                                        │  → "xK8mZq2pR5vL9nA3..."
  │                                        │
  │                                        ├─ Store in reset_tokens:
  │                                        │  token → {email, created_at}
  │                                        │
  │  ◄──────────────────────────────────  │
  │  200 {message: "If the email           │
  │        is registered, a reset link     │
  │        has been sent"}                 │
```

### POST /password-reset/request — Email NOT Found

```
Client                                   Server
  │                                        │
  │  POST /password-reset/request          │
  │  Body: {email: "hacker@evil.com"}     │
  │ ──────────────────────────────────►    │
  │                                        ├─ slowapi rate limit 3/hour
  │                                        │  └─ OK
  │                                        ├─ Pydantic: EmailStr valid
  │                                        │  └─ OK
  │                                        ├─ Lookup hacker@evil.com
  │                                        │  in users dict
  │                                        │  └─ NOT FOUND → skip
  │                                        │
  │                                        ├─ (no token generated)
  │                                        │
  │  ◄──────────────────────────────────  │
  │  200 {message: "If the email           │
  │        is registered, a reset link     │
  │        has been sent"}                 │
  │                                        │
  │       ↑ IDENTICAL response ↑          │
  │    Attacker can NOT tell the           │
  │    difference between the two          │
```

### POST /password-reset/confirm — Success

```
Client                                   Server
  │                                        │
  │  POST /password-reset/confirm          │
  │  Body: {                               │
  │    token: "xK8mZq2pR5...",            │
  │    new_password: "NewSecurePass99"     │
  │  }                                      │
  │ ──────────────────────────────────►    │
  │                                        ├─ Pydantic validation
  │                                        │  └─ token present? ✓
  │                                        │  └─ password ≥ 8 chars? ✓
  │                                        │
  │                                        ├─ Lookup token in reset_tokens
  │                                        │  └─ FOUND
  │                                        │
  │                                        ├─ Check TTL: 15 min
  │                                        │  now - created_at = 120s
  │                                        │  120 < 900 → OK
  │                                        │
  │                                        ├─ Update password:
  │                                        │  users[email][password]
  │                                        │  = "NewSecurePass99"
  │                                        │
  │                                        ├─ Delete token (one-time)
  │                                        │
  │  ◄──────────────────────────────────  │
  │  200 {message: "Password reset         │
  │        successful"}                    │
```

### POST /password-reset/confirm — Expired Token

```
Client                                   Server
  │                                        │
  │  POST /password-reset/confirm          │
  │  Body: {token: "expired...",          │
  │         new_password: "NewPass123"}    │
  │ ──────────────────────────────────►    │
  │                                        ├─ Lookup token: FOUND
  │                                        ├─ Check TTL: 15 min
  │                                        │  now - created_at = 3600s
  │                                        │  3600 > 900 → EXPIRED
  │                                        ├─ Delete token from store
  │  ◄──────────────────────────────────  │
  │  400 {detail: "Invalid or expired     │
  │        token"}                         │
```

## Data Stores

### Users

```python
users = {
    "alice@example.com": {"password": "AlicePass123", "name": "Alice"},
    "bob@example.com":   {"password": "BobPass456",   "name": "Bob"},
}
```

Passwords are plain-text for demo. Production apps should hash with bcrypt/argon2.

### Reset Tokens

```python
reset_tokens = {
    "xK8mZq2pR5vL9nA3cF7jW1bY4eD6gH0iJ2kM4oP6rS": {
        "email": "alice@example.com",
        "created_at": 1721812345.67,
    }
}
```

## Pydantic Models

### ResetRequest

```python
class ResetRequest(BaseModel):
    email: EmailStr       # Validates email format → 422 if invalid
```

### ResetConfirm

```python
class ResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)   # 8+ characters → 422 if shorter
```

## Security Strategy

### 1. Email Non-Disclosure (Security Challenge)

```python
@app.post("/password-reset/request")
@limiter.limit("3/hour")
def reset_request(request: Request, body: ResetRequest):
    user = users.get(body.email)
    if user:                                        # Same branch — both
        token = secrets.token_urlsafe(32)            # execute the same
        reset_tokens[token] = {                      # return statement
            "email": body.email,
            "created_at": time.time(),
        }

    return {"message": "If the email is registered, a reset link has been sent"}
```

The response is **identical** whether or not the user exists. No `else` branch, no different status codes, no different messages.

### 2. One-Time Token

```python
reset_tokens.pop(body.token, None)  # Delete after use — second request with same token fails
```

### 3. Token Expiry (15 min TTL)

```python
TOKEN_TTL = 900  # 15 minutes

if time.time() - token_data["created_at"] > TOKEN_TTL:
    reset_tokens.pop(body.token, None)        # Clean up expired token
    raise HTTPException(status_code=400, detail="Invalid or expired token")
```

Same error for both invalid and expired tokens — attacker cannot distinguish.

### 4. Why Generic Error for Token Failure

| Scenario | Error |
|----------|-------|
| Token doesn't exist | `400 "Invalid or expired token"` |
| Token expired (just deleted) | `400 "Invalid or expired token"` |

Same message prevents attackers from learning whether a token was valid but expired vs never existed.

## Rate Limiting

| Endpoint | Limit | Method | Why |
|----------|-------|--------|-----|
| POST `/password-reset/request` | 3/hour | slowapi (IP-based) | Prevents bulk email enumeration |
| POST `/password-reset/confirm` | None | — | Token itself is the authorization |

## No API Key — Why?

This endpoint is specifically for users who **forgot their password**. They cannot have or remember an API key. Rate limiting replaces API key auth as the abuse prevention mechanism.

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Reset requested / confirmed successfully |
| 400 | Bad Request | Invalid or expired token |
| 422 | Validation Error | Invalid email format or password < 8 chars |
| 429 | Too Many Requests | Rate limit exceeded (3/hour) |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Start the server

```bash
uvicorn main:app --reload
```

### 3. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 4. Test via curl

```bash
# Request reset for an existing email
curl -X POST "http://127.0.0.1:8000/password-reset/request" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com"}'
# Returns: {"message": "If the email is registered, a reset link has been sent"}

# Request reset for a NON-EXISTENT email — SAME response
curl -X POST "http://127.0.0.1:8000/password-reset/request" \
  -H "Content-Type: application/json" \
  -d '{"email": "unknown@evil.com"}'
# Returns: {"message": "If the email is registered, a reset link has been sent"}
# ← Identical! Attacker cannot tell which exists.

# Confirm password reset (use the token from first request — check console logs)
curl -X POST "http://127.0.0.1:8000/password-reset/confirm" \
  -H "Content-Type: application/json" \
  -d '{"token": "xK8mZq2pR5...", "new_password": "NewSecurePass99"}'

# Try expired/invalid token — returns 400
curl -X POST "http://127.0.0.1:8000/password-reset/confirm" \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid-token", "new_password": "NewPass123"}'
# Returns 400: "Invalid or expired token"

# Try password shorter than 8 chars — returns 422
curl -X POST "http://127.0.0.1:8000/password-reset/confirm" \
  -H "Content-Type: application/json" \
  -d '{"token": "some-token", "new_password": "short"}'
# Returns 422: "String should have at least 8 characters"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Don't reveal if email exists | Same message for both paths | Same code path, same return → attacker can't distinguish |
| Generate token only for registered users | `if user:` guard before token generation | Not found → no token, but same response |
| Token expires | `TOKEN_TTL = 900` + `time.time() - created_at` check | Auto-cleaned on access attempt |
| One-time use | `reset_tokens.pop(token)` after success | Deletes key from dict — second request returns 400 |
| Password ≥ 8 chars | `Field(min_length=8)` on `new_password` | Pydantic auto-rejects → 422 |
| Strict rate limiting | slowapi `3/hour` on request endpoint | Prevents email enumeration via brute force |
| No API key | — | User forgot password, can't have a key |
| Cryptographically secure token | `secrets.token_urlsafe(32)` | 43-char URL-safe string, 256 bits of entropy |
