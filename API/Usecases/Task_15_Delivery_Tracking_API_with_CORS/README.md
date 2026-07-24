# Delivery Tracking API with CORS

A secure FastAPI-based delivery tracking system with CORS configured for two specific frontend origins (customer website and admin dashboard), admin-only status updates, and a strict tracking status enum.

## Features

- Customer website (`https://track.company.com`) can call only GET
- Admin dashboard (`https://admin.company.com`) can call GET and PATCH
- Only exact frontend origins allowed — no wildcard CORS
- Tracking status enforced via enum: `created`, `picked_up`, `in_transit`, `out_for_delivery`, `delivered`, `failed`
- Admin PATCH requires X-Admin-Key header
- Returns 404 for invalid tracking IDs
- CORS does NOT replace authentication — explained in detail below

## Architecture

```
┌─────────────────────┐      ┌─────────────────────┐
│  track.company.com  │      │ admin.company.com   │
│  (Customer Website) │      │ (Admin Dashboard)   │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           │  GET /tracking/{id}        │  GET /tracking/{id}
           │  (CORS allows GET)         │  PATCH /tracking/{id}
           │                            │  + X-Admin-Key header
           ▼                            ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              CORS Middleware                      │    │
│  │                                                   │    │
│  │  Allows:                                          │    │
│  │    track.company.com  → GET                       │    │
│  │    admin.company.com  → GET, PATCH                │    │
│  │                                                   │    │
│  │  Rejects:                                         │    │
│  │    evil-site.com     → blocked by browser         │    │
│  │    curl/Postman      → NOT blocked (CORS is       │    │
│  │                         browser-only!)             │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Route Handlers                       │    │
│  │                                                   │    │
│  │  GET /tracking/{id}                               │    │
│  │    No auth — any origin can view tracking         │    │
│  │                                                   │    │
│  │  PATCH /tracking/{id}                             │    │
│  │    Requires X-Admin-Key (Security guard)           │    │
│  │    Rejects invalid status via enum                │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                   │    │
│  │  packages = {                                     │    │
│  │    "TKT001": {tracking_id, status, origin,        │    │
│  │               destination, last_updated},         │    │
│  │    "TKT002": {...}                                │    │
│  │  }                                                 │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | CORS Allowed From | Description |
|--------|------|------|-------------------|-------------|
| GET | `/tracking/{id}` | None | Both origins | View package tracking |
| PATCH | `/tracking/{id}` | X-Admin-Key | Admin origin only | Update tracking status |
| GET | `/health` | None | Both origins | Health check |

## CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://track.company.com",
        "https://admin.company.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "PATCH"],
    allow_headers=["content-type", "X-Admin-Key"],
)
```

### Why Exact Origins?

Using `allow_origins=["*"]` would allow **any website** (including attacker sites) to make browser requests to the API. By whitelisting only `track.company.com` and `admin.company.com`, we ensure that only our own frontends can make cross-origin requests from the browser.

### Why CORS Does NOT Replace Authentication

This is the **security challenge** for this task.

| Aspect | CORS | Auth (API Key) |
|--------|------|----------------|
| **Enforced by** | Browser | Server |
| **Can be bypassed?** | Yes — curl, Postman, server-side scripts | No — key must be valid |
| **Purpose** | Controls which web origins can make browser requests | Controls who can access/modify data |
| **Scope** | Browser only | All HTTP clients |

**CORS is a browser policy, not a security boundary.** It tells the browser: "this API is safe to call from these origins." But any attacker with curl or a server-side script can bypass CORS entirely — they just don't send an `Origin` header.

**PATCH still requires X-Admin-Key.** CORS alone would never prevent a malicious actor from updating tracking statuses. The API key is the actual authentication mechanism. CORS simply adds an extra layer for browser-based scenarios (e.g., preventing a random blog from making authenticated PATCH requests via the admin's logged-in browser session).

> **One-liner:** CORS is a browser setting that politely asks "please don't send my data to other sites" — it's not a lock on the door. Authentication is the lock.

## Code Flow Diagrams

### GET /tracking/{tracking_id} — Customer Website

```
Browser (track.company.com)             Server
  │                                        │
  │  GET /tracking/TKT001                  │
  │  Origin: https://track.company.com     │
  │ ──────────────────────────────────►    │
  │                                        ├─ CORS: track.company.com
  │                                        │  is in allow_origins? ✓
  │                                        │
  │                                        ├─ Lookup "TKT001"
  │                                        │  └─ Not found → 404
  │                                        │
  │  ◄──────────────────────────────────  │
  │  200 {tracking_id: "TKT001",           │
  │       status: "in_transit",            │
  │       origin: "New York, NY",          │
  │       destination: "Los Angeles, CA",  │
  │       last_updated: "2025-07-24T..."}  │
```

### GET /tracking/{tracking_id} — Attacker Website (Blocked by CORS)

```
Browser (evil-site.com)                 Server
  │                                        │
  │  GET /tracking/TKT001                  │
  │  Origin: https://evil-site.com        │
  │ ──────────────────────────────────►    │
  │                                        ├─ CORS: evil-site.com
  │                                        │  is in allow_origins?
  │                                        │  └─ NO
  │                                        │
  │  (Server responds with data, but      │
  │   browser BLOCKS the response from    │
  │   being read by JavaScript because     │
  │   CORS headers don't include           │
  │   evil-site.com)                       │
  │                                        │
  │  ◄─── BLOCKED BY BROWSER ───►         │
  │  Console: CORS error                  │
```

### PATCH /tracking/{tracking_id} — Admin Dashboard

```
Browser (admin.company.com)             Server
  │                                        │
  │  OPTIONS /tracking/TKT001              │
  │  (Preflight — browser checks CORS)    │
  │  Origin: https://admin.company.com    │
  │  Access-Control-Request-Method: PATCH │
  │ ──────────────────────────────────►    │
  │                                        ├─ CORS: check origin ✓
  │                                        ├─ CORS: check method ✓
  │  ◄──────────────────────────────────  │
  │  200 CORS headers returned             │
  │                                        │
  │  PATCH /tracking/TKT001                │
  │  Origin: https://admin.company.com    │
  │  Headers: X-Admin-Key: <key>          │
  │  Body: {status: "delivered"}          │
  │ ──────────────────────────────────►    │
  │                                        ├─ CORS: origin allowed ✓
  │                                        ├─ Security(require_admin_key)
  │                                        │  └─ Invalid → 401
  │                                        ├─ Lookup "TKT001"
  │                                        │  └─ Not found → 404
  │                                        ├─ Pydantic validate status
  │                                        │  └─ Invalid enum → 422
  │                                        ├─ Update status + timestamp
  │  ◄──────────────────────────────────  │
  │  200 {message: "Status updated",       │
  │       tracking_id: "TKT001",          │
  │       status: "delivered",            │
  │       last_updated: "2025-07-24T..."} │
```

### PATCH — Bypassing CORS via curl (Why Auth Matters)

```
Attacker's terminal                    Server
  │                                        │
  │  curl -X PATCH ...                     │
  │  (curl doesn't check CORS)            │
  │  Headers: X-Admin-Key: garbage        │
  │ ──────────────────────────────────►    │
  │                                        ├─ CORS: curl doesn't send
  │                                        │  Origin header → no check
  │                                        ├─ Security(require_admin_key)
  │                                        │  └─ Wrong key → 401
  │                                        │
  │  ◄──────────────────────────────────  │
  │  401 {"detail": "Invalid or missing   │
  │        API key"}                       │
  │                                        │
  │     ↑ AUTH blocked it, not CORS ↑     │
```

## Tracking Status Enum

```python
class TrackingStatus(str, Enum):
    created = "created"
    picked_up = "picked_up"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    failed = "failed"
```

Any string not in this list (e.g. `"shipped"`, `"lost"`) is rejected by Pydantic with 422.

## Pre-loaded Packages

```python
packages = {
    "TKT001": {
        "tracking_id": "TKT001",
        "status": "in_transit",
        "origin": "New York, NY",
        "destination": "Los Angeles, CA",
        "last_updated": "2025-07-24T10:30:00Z",
    },
    "TKT002": {
        "tracking_id": "TKT002",
        "status": "out_for_delivery",
        "origin": "Chicago, IL",
        "destination": "Austin, TX",
    },
    # ... TKT003, TKT004 ...
}
```

## Pydantic Models

### StatusUpdate

```python
class StatusUpdate(BaseModel):
    status: TrackingStatus         # Enum — auto rejects invalid values as 422
```

## Auth Strategy

| Header | Env Var | Endpoint | Purpose |
|--------|---------|----------|---------|
| `X-Admin-Key` | `ADMIN_KEY` | `PATCH /tracking/{id}` | Admin-only status updates |

The GET endpoint has **no auth** — customers should be able to track their package without any credentials.

```python
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False, scheme_name="admin-key")

def require_admin_key(key: str = Security(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Tracking data retrieved or updated |
| 401 | Unauthorized | Invalid or missing admin key |
| 404 | Not Found | Tracking ID not found |
| 422 | Validation Error | Invalid tracking status value |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

### 2. Set API key

A `.env` file is provided with a default key. Change it for production:

```
ADMIN_KEY=admin-secret-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs — the `admin-key` Authorize field appears for the PATCH endpoint.

### 5. Test via curl

```bash
# Customer — view tracking (no auth required)
curl -X GET "http://127.0.0.1:8000/tracking/TKT001"

# Admin — update tracking status
curl -X PATCH "http://127.0.0.1:8000/tracking/TKT001" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"status": "delivered"}'

# Invalid tracking ID — returns 404
curl -X GET "http://127.0.0.1:8000/tracking/INVALID"

# No admin key — returns 401
curl -X PATCH "http://127.0.0.1:8000/tracking/TKT001" \
  -H "Content-Type: application/json" \
  -d '{"status": "delivered"}'

# Invalid status — returns 422
curl -X PATCH "http://127.0.0.1:8000/tracking/TKT001" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"status": "lost"}'
```

### 6. Testing CORS locally

To test CORS behavior locally, modify the origins to include your local dev server:

```python
allow_origins=[
    "http://localhost:3000",    # Customer frontend dev server
    "http://localhost:3001",    # Admin dashboard dev server
]
```

Then serve a simple HTML page from `http://localhost:3000` and try to fetch the API from `http://127.0.0.1:8000`.

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Customer can only GET | No auth on GET, method restricted in CORS | Customers track packages without credentials |
| Admin can GET and PATCH | X-Admin-Key on PATCH, both methods in CORS | Admin origin can do both |
| Exact origins only | `allow_origins=[...]` with full URLs | No wildcard — prevents unauthorized origins |
| Status validated | `TrackingStatus` enum | Invalid values auto-rejected as 422 |
| 404 for invalid tracking IDs | `packages.get(id)` check | Generic 404, no info leakage |
| CORS doesn't replace auth | Security guard on PATCH | curl bypasses CORS; auth prevents that |
