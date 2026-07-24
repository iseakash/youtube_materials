# API Usage Plan and Subscription Limiting API

A secure FastAPI-based API subscription management system with three plans (Free, Pro, Enterprise), each with different per-minute request limits enforced per API key.

## Features

- Three subscription plans with different rate limits:
  - **Free**: 5 requests per minute
  - **Pro**: 20 requests per minute
  - **Enterprise**: 100 requests per minute
- Plan identified via API key (loaded from `.env`)
- Rate limiting enforced **per API key**, not per IP
- Returns current plan and remaining requests in every response
- Returns 401 for unknown API keys
- Returns 429 when plan limit is exceeded

## Architecture

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │  GET /data
       │  Headers: X-API-Key
       ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │               Request Pipeline                     │    │
│  │                                                    │    │
│  │  1. Extract X-API-Key header                      │    │
│  │     └─ Missing → 401                              │    │
│  │                                                    │    │
│  │  2. Look up key in API_KEYS dict                  │    │
│  │     └─ Unknown key → 401                          │    │
│  │     └─ Found → get plan + limit                   │    │
│  │                                                    │    │
│  │  3. Check rate_tracker for this key               │    │
│  │     Filter timestamps within last 60 seconds       │    │
│  │     └─ Count ≥ plan limit → 429                   │    │
│  │                                                    │    │
│  │  4. ✓ ALL PASS                                    │    │
│  │     Append current timestamp to tracker            │    │
│  │     Calculate remaining = limit - count            │    │
│  │     Return plan info + remaining to handler        │    │
│  │                                                    │    │
│  │  5. Handler returns data + plan + remaining        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                    │    │
│  │  API_KEYS = {                                     │    │
│  │    "free-key-001":   {"plan": "free",  limit: 5}, │    │
│  │    "pro-key-002":    {"plan": "pro",   limit: 20},│    │
│  │    "enterprise-key": {"plan": "enterprise",       │    │
│  │                       "limit": 100}                │    │
│  │  }                                                  │    │
│  │                                                    │    │
│  │  rate_tracker = {                                  │    │
│  │    "free-key-001": [ts1, ts2, ts3, ...],          │    │
│  │    "pro-key-002":  [ts4, ts5, ...],               │    │
│  │  }   ← keyed by API key, not IP                   │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/data` | X-API-Key | Per-plan (5/20/100 per min) | Access data with plan info |
| GET | `/health` | None | None | Health check |

## Code Flow Diagrams

### GET /data — Successful Request

```
Client                                   Server
  │                                        │
  │  GET /data                             │
  │  Headers: X-API-Key: free-key-001     │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(verify_and_throttle)
  │                                        │  │
  │                                        │  ├─ Extract X-API-Key header
  │                                        │  │  └─ Missing? → 401
  │                                        │  │
  │                                        │  ├─ Lookup "free-key-001" in API_KEYS
  │                                        │  │  └─ Not found? → 401
  │                                        │  │  └─ Found: {plan: "free", limit: 5}
  │                                        │  │
  │                                        │  ├─ Get timestamps for "free-key-001"
  │                                        │  │     from rate_tracker
  │                                        │  ├─ Filter: keep only timestamps
  │                                        │  │     where now - ts < 60 seconds
  │                                        │  ├─ Count = 3, limit = 5
  │                                        │  │  └─ 3 >= 5? No → OK
  │                                        │  │
  │                                        │  ├─ Append current timestamp
  │                                        │  ├─ Calculate remaining = 5 - 4 = 1
  │                                        │  └─ Return {plan: "free", remaining: 1}
  │                                        │
  │                                        ├─ Handler receives usage dict
  │  ◄──────────────────────────────────  │
  │  200 {                                 │
  │    "data": [...],                       │
  │    "plan": "free",                      │
  │    "requests_remaining": 1              │
  │  }                                      │
```

### GET /data — Rate Limited (429)

```
Client                                   Server
  │                                        │
  │  GET /data (6th request in 60s)       │
  │  Headers: X-API-Key: free-key-001     │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(verify_and_throttle)
  │                                        │  │
  │                                        │  ├─ Key found: plan="free", limit=5
  │                                        │  ├─ Filter timestamps: 5 in last 60s
  │                                        │  ├─ Count = 5 ≥ limit = 5
  │                                        │  │  └─ RAISE 429
  │  ◄──────────────────────────────────  │
  │  429 {                                 │
  │    "detail": "Rate limit exceeded     │
  │               for your plan"           │
  │  }                                      │
```

### GET /data — Unknown API Key (401)

```
Client                                   Server
  │                                        │
  │  GET /data                             │
  │  Headers: X-API-Key: invalid-key      │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(verify_and_throttle)
  │                                        │  ├─ Lookup "invalid-key" in API_KEYS
  │                                        │  │  └─ Not found → RAISE 401
  │  ◄──────────────────────────────────  │
  │  401 {"detail": "Invalid or missing   │
  │        API key"}                       │
```

## Data Stores

### API_KEYS Lookup Table

```python
API_KEYS = {
    "free-key-001":       {"plan": "free",       "limit": 5},
    "pro-key-002":        {"plan": "pro",        "limit": 20},
    "enterprise-key-003": {"plan": "enterprise", "limit": 100},
}
```

Keys are loaded from `.env` via `os.getenv()` — never hard-coded.

### rate_tracker (Per-Key Rolling Window)

```python
rate_tracker = {
    "free-key-001": [1721812345.67, 1721812350.12, ...],  # Unix timestamps
    "pro-key-002":  [1721812300.00, ...],
}
```

- Each request appends `time.time()` to the key's list
- Old entries (> 60s) are filtered out on each check
- Self-cleaning: no background cleanup needed

## Auth Strategy

| Header | Source | Purpose |
|--------|--------|---------|
| `X-API-Key` | `.env` (FREE_KEY, PRO_KEY, ENTERPRISE_KEY) | Identify plan + throttle |

```python
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")

def verify_and_throttle(key: str = Security(api_key_header)):
    if key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    plan_info = API_KEYS[key]
    now = time.time()
    window = 60

    timestamps = [t for t in rate_tracker.get(key, []) if now - t < window]

    if len(timestamps) >= plan_info["limit"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for your plan")

    timestamps.append(now)
    rate_tracker[key] = timestamps

    return {"plan": plan_info["plan"], "remaining": plan_info["limit"] - len(timestamps)}
```

## Subscription Plans

| Plan | API Key (in .env) | Limit (per minute) |
|------|--------------------|--------------------|
| Free | `FREE_KEY=free-key-001` | 5 |
| Pro | `PRO_KEY=pro-key-002` | 20 |
| Enterprise | `ENTERPRISE_KEY=enterprise-key-003` | 100 |

## Security Challenge — Per-Key Rate Limiting

> Rate limiting must happen per API key, not only per IP address.

Two users behind the same NAT (same public IP) with different API keys get **separate** rate limits:

```
User A (free-key-001):  5/min  ─┐
                                 ├─ same IP, different limits
User B (pro-key-002):   20/min ─┘
```

The `rate_tracker` dict is keyed by the API key value itself, not by `get_remote_address()`. This is why we build a custom rate limiter instead of using slowapi.

## Why Not slowapi?

| Factor | slowapi | Custom (this task) |
|--------|---------|-------------------|
| Key function | Fixed (e.g. IP) | API key value |
| Limit string | Static (`"5/minute"`) | Dynamic per key (5, 20, or 100) |
| Plan detection | Not possible | Built into guard function |
| Return plan info | Not possible | Returns `{plan, remaining}` |
| Per-key tracking | Via key function | `rate_tracker[key]` dict |

## `Security()` in Task 12 vs Previous Tasks

In Tasks 8–11, `Security()` was used purely as an **auth gate** — the guard function returned the raw API key string, but the handler never used it:

```python
# Previous tasks — Security() returns the key string, handler ignores it
def create_ticket(key: str = Security(require_customer_key)):
    # key = "customer-secret-key-2024" — captured but never used in the body
```

In Task 12, `verify_and_throttle` does **double duty**: it authenticates, throttles, **and returns a computed dict** that the handler actively consumes:

```python
# Task 12 — Security() returns {plan, remaining} dict, handler uses it
def get_data(usage: dict = Security(verify_and_throttle)):
    # usage = {"plan": "free", "remaining": 4} — used in the response body
    return {"plan": usage["plan"], "requests_remaining": usage["remaining"], ...}
```

| Aspect | Tasks 8–11 | Task 12 |
|--------|------------|---------|
| Guard returns | `str` (the API key) | `dict` (plan info + remaining) |
| Handler uses it? | No — captured but ignored | Yes — reads `usage["plan"]`, `usage["remaining"]` |
| Parameter name | `key` | `usage` (semantic — describes what it holds) |
| Why? | Auth was a pure gate | Auth + throttle + data enrichment in one dependency |

The handler parameter name `usage` reflects its content — it carries the user's current plan usage statistics, not just an auth credential.

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Successful data response |
| 401 | Unauthorized | Invalid or missing API key |
| 429 | Too Many Requests | Per-plan rate limit exceeded |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

### 2. Set API keys

A `.env` file is provided with default keys. Change them for production:

```
FREE_KEY=free-key-001
PRO_KEY=pro-key-002
ENTERPRISE_KEY=enterprise-key-003
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs — click Authorize and enter one of the keys.

### 5. Test via curl

```bash
# Free plan — 5 requests per minute
curl -X GET "http://127.0.0.1:8000/data" \
  -H "X-API-Key: free-key-001"

# Pro plan — 20 requests per minute
curl -X GET "http://127.0.0.1:8000/data" \
  -H "X-API-Key: pro-key-002"

# Enterprise plan — 100 requests per minute
curl -X GET "http://127.0.0.1:8000/data" \
  -H "X-API-Key: enterprise-key-003"

# Invalid key — returns 401
curl -X GET "http://127.0.0.1:8000/data" \
  -H "X-API-Key: wrong-key"

# Hit rate limit — run this 6 times quickly
for ($i=0; $i -lt 6; $i++) {
  curl -s -X GET "http://127.0.0.1:8000/data" `
    -H "X-API-Key: free-key-001"
}
# 6th request returns 429
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Plan identified via API key | `API_KEYS` lookup dict | Keys loaded from `.env`, never hard-coded |
| Free: 5/min, Pro: 20/min, Enterprise: 100/min | `limit` value in `API_KEYS` dict | Dynamic — guard reads plan_info for each request |
| Per-key rate limiting | `rate_tracker[key]` dict of timestamps | Not IP-based — two users same IP, different keys get separate limits |
| Rolling 60-second window | Filter timestamps: `now - ts < 60` | Self-cleaning — old entries naturally drop off |
| Return plan in response | `usage["plan"]` from guard | Sent to handler via Security return value |
| Return remaining requests | Calculated after appending timestamp | Accurate count reflects the just-completed request |
| 401 for unknown keys | `key not in API_KEYS` | Generic message prevents key enumeration |
| 429 when limit exceeded | `len(timestamps) >= limit` | Checked before appending current timestamp |
