# Coupon Management API

A secure FastAPI-based coupon management system with role-based access (admin creates/deletes, customers validate), future-expiry enforcement, minimum order validation, and controlled error messages.

## Features

- Admin creates coupons with discount 1–80%, future expiry, optional minimum order value
- Admin deletes coupons by code
- Customers validate coupons against an order amount
- Coupon codes must be uppercase alphanumeric with underscores (regex enforced)
- Expired, inactive, or insufficient-order coupons return controlled 400 errors
- Unique coupon codes enforced (409 on duplicate)
- 403 Forbidden when customer key used on admin endpoints
- Two separate API key headers using `Security()` for Swagger UI Authorize

## Architecture

```
┌──────────────┐          ┌──────────────┐
│   Admin      │          │   Customer   │
└──────┬───────┘          └──────┬───────┘
       │  X-Admin-Key            │  X-Customer-Key
       │                         │
       │  POST /admin/coupons    │  GET /coupons/validate
       │  DELETE /admin/coupons/ │  ?code=SAVE20
       │    {coupon_code}        │  &order_value=1000
       ▼                         ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Admin Endpoints (X-Admin-Key)             │    │
│  │                                                    │    │
│  │  POST /admin/coupons:                              │    │
│  │    ├─ Security(require_admin)                     │    │
│  │    │  ├─ Customer key? → 403                      │    │
│  │    │  └─ Invalid/missing → 401                    │    │
│  │    ├─ Pydantic validate body                      │    │
│  │    ├─ Check code uniqueness                       │    │
│  │    ├─ Check future expiry                         │    │
│  │    └─ Store coupon                                │    │
│  │                                                    │    │
│  │  DELETE /admin/coupons/{code}:                     │    │
│  │    ├─ Security(require_admin)                     │    │
│  │    ├─ Lookup code                                 │    │
│  │    └─ Delete from dict                            │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │       Customer Endpoint (X-Customer-Key)          │    │
│  │                                                    │    │
│  │  GET /coupons/validate:                            │    │
│  │    ├─ Security(require_customer)                  │    │
│  │    ├─ Pydantic validate query params              │    │
│  │    ├─ Lookup coupon code                          │    │
│  │    ├─ Check is_active                             │    │
│  │    ├─ Check expiry                                │    │
│  │    ├─ Check min_order_value                       │    │
│  │    └─ Calculate discount + return                 │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                    │    │
│  │  coupons = {                                      │    │
│  │    "SAVE20": {code, discount_percent,             │    │
│  │               expiry, min_order_value,            │    │
│  │               is_active},                          │    │
│  │    "WELCOME10": {...}                              │    │
│  │  }                                                  │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/admin/coupons` | X-Admin-Key | Create a new coupon |
| DELETE | `/admin/coupons/{coupon_code}` | X-Admin-Key | Delete an existing coupon |
| GET | `/coupons/validate` | X-Customer-Key | Validate a coupon against an order |
| GET | `/health` | None | Health check |

## Auth Strategy

| Header | Env Var | Endpoints | Purpose |
|--------|---------|-----------|---------|
| `X-Admin-Key` | `ADMIN_KEY` | POST/DELETE `/admin/*` | Admin coupon management |
| `X-Customer-Key` | `CUSTOMER_KEY` | GET `/coupons/validate` | Customer validation |

### 403 Logic — Customer Cannot Access Admin

```python
def require_admin(key: str = Security(admin_key_header)):
    if key == CUSTOMER_KEY:                        # Valid key, but wrong role
        raise HTTPException(status_code=403, detail="Admin access required")
    if key != ADMIN_KEY:                           # Missing or invalid
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
```

| What they send in X-Admin-Key | Result |
|------------------------------|--------|
| Nothing / garbage key | 401 |
| The customer key | 403 Forbidden |
| The admin key | ✅ Allowed |

## Code Flow Diagrams

### POST /admin/coupons — Create Coupon

```
Admin                                     Server
  │                                        │
  │  POST /admin/coupons                   │
  │  Headers: X-Admin-Key                  │
  │  Body: {code: "FLAT50",               │
  │         discount_percent: 50,          │
  │         expiry: "2025-12-31",          │
  │         min_order_value: 1000}         │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_admin)
  │                                        │  ├─ key == CUSTOMER_KEY → 403
  │                                        │  ├─ key != ADMIN_KEY → 401
  │                                        │  └─ OK
  │                                        │
  │                                        ├─ Pydantic validates body
  │                                        │  └─ Invalid → 422
  │                                        │
  │                                        ├─ "FLAT50" in coupons dict?
  │                                        │  └─ Exists → 409
  │                                        │
  │                                        ├─ expiry ≤ today?
  │                                        │  └─ Yes → 400
  │                                        │
  │                                        ├─ ✓ ALL PASS
  │                                        ├─ Store in coupons dict
  │  ◄──────────────────────────────────  │
  │  201 {message, coupon: {code,          │
  │       discount_percent, expiry,        │
  │       min_order_value, is_active}}     │
```

### DELETE /admin/coupons/{coupon_code} — Delete Coupon

```
Admin                                     Server
  │                                        │
  │  DELETE /admin/coupons/SAVE20          │
  │  Headers: X-Admin-Key                  │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_admin)
  │                                        │  └─ 401/403 check
  │                                        │
  │                                        ├─ Lookup "SAVE20"
  │                                        │  └─ Not found → 404
  │                                        │
  │                                        ├─ Delete from dict
  │  ◄──────────────────────────────────  │
  │  200 {message: "Coupon deleted         │
  │        successfully"}                  │
```

### GET /coupons/validate — Validate Coupon

```
Customer                                  Server
  │                                        │
  │  GET /coupons/validate                 │
  │  ?code=SAVE20&order_value=1000         │
  │  Headers: X-Customer-Key               │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_customer)
  │                                        │  └─ Invalid → 401
  │                                        │
  │                                        ├─ Pydantic validates query
  │                                        │  └─ Invalid → 422
  │                                        │
  │                                        ├─ Lookup "SAVE20"
  │                                        │  └─ Not found → 404
  │                                        │
  │                                        ├─ is_active = False?
  │                                        │  └─ Yes → 400
  │                                        │
  │                                        ├─ expiry < today?
  │                                        │  └─ Yes → 400
  │                                        │
  │                                        ├─ min_order_value = 500
  │                                        │  order_value = 1000
  │                                        │  1000 < 500? No → OK
  │                                        │
  │                                        ├─ Calculate:
  │                                        │  discount = 20% × 1000 = 200
  │                                        │  final = 1000 - 200 = 800
  │  ◄──────────────────────────────────  │
  │  200 {valid: true, code: "SAVE20",     │
  │       discount_percent: 20,            │
  │       discount_amount: 200,            │
  │       original_amount: 1000,           │
  │       final_amount: 800}               │
```

## Validation Order

### POST /admin/coupons
```
1. Auth (X-Admin-Key)                    → 401/403
2. Pydantic body validation              → 422
3. Code uniqueness                       → 409
4. Future expiry                         → 400
5. ─── ALL PASS → Store coupon ───           201
```

### GET /coupons/validate
```
1. Auth (X-Customer-Key)                 → 401
2. Pydantic query validation             → 422
3. Coupon code exists?                   → 404
4. Coupon is active?                     → 400
5. Coupon is not expired?                → 400
6. Order value ≥ min_order_value?        → 400
7. ─── ALL PASS → Calculate + return         200
```

## Pydantic Models

### CouponCreate

```python
class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z0-9_]+$")
    discount_percent: int = Field(ge=1, le=80)
    expiry: date
    min_order_value: float | None = Field(default=None, ge=0)
```

- `code` — 3–20 chars, only uppercase letters, digits, and underscores
- `discount_percent` — 1% to 80%
- `expiry` — must be a future date (validated manually in handler)
- `min_order_value` — optional, must be ≥ 0 if provided

### CouponValidateQuery

```python
class CouponValidateQuery(BaseModel):
    code: str
    order_value: float = Field(gt=0)
```

Used for query parameter validation via `Query(...)` on the endpoint.

## Coupon Code Pattern

```
^[A-Z0-9_]+$
```

Valid: `SAVE20`, `WELCOME10`, `FLAT_50`, `NEWUSER`
Invalid: `save20` (lowercase), `HELLO-WORLD` (hyphen), `abc` (too short)

## Pre-loaded Coupons

```python
coupons = {
    "SAVE20": {
        "code": "SAVE20",
        "discount_percent": 20,
        "expiry": "2025-12-31",
        "min_order_value": 500.0,
        "is_active": True,
    },
    "WELCOME10": {
        "code": "WELCOME10",
        "discount_percent": 10,
        "expiry": "2026-06-30",
        "min_order_value": None,
        "is_active": True,
    },
}
```

## Security Challenge

> Customers must never be able to create or delete coupons.

| Attempt | Header Used | Result | Why |
|---------|-------------|--------|-----|
| Customer calls POST `/admin/coupons` | `X-Admin-Key: <customer-key>` | **403 Forbidden** | `require_admin` detects the key matches CUSTOMER_KEY |
| Stranger calls POST `/admin/coupons` | `X-Admin-Key: garbage` | **401 Unauthorized** | Key doesn't match ADMIN_KEY |
| Customer calls GET `/coupons/validate` | `X-Customer-Key: <customer-key>` | ✅ 200 | Correct key for customer endpoint |
| Admin calls GET `/coupons/validate` | `X-Customer-Key: <admin-key>` | **401** | Admin key doesn't match CUSTOMER_KEY |

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Coupon deleted or validated |
| 201 | Created | Coupon created |
| 400 | Bad Request | Expired coupon, inactive, or min order not met |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Customer key used on admin endpoint |
| 404 | Not Found | Coupon code doesn't exist |
| 409 | Conflict | Coupon code already exists |
| 422 | Validation Error | Pydantic field/pattern/constraint violations |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

### 2. Set API keys

A `.env` file is provided with default keys. Change them for production:

```
ADMIN_KEY=admin-secret-key-2024
CUSTOMER_KEY=customer-secret-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs — both `admin-key` and `customer-key` Authorize fields appear.

### 5. Test via curl

```bash
# Admin creates a coupon
curl -X POST "http://127.0.0.1:8000/admin/coupons" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"code": "FLAT50", "discount_percent": 50, "expiry": "2025-12-31", "min_order_value": 1000}'

# Customer validates a coupon
curl -X GET "http://127.0.0.1:8000/coupons/validate?code=SAVE20&order_value=1000" \
  -H "X-Customer-Key: customer-secret-key-2024"

# Customer tries to create a coupon — 403
curl -X POST "http://127.0.0.1:8000/admin/coupons" \
  -H "X-Admin-Key: customer-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"code": "HACKED", "discount_percent": 90, "expiry": "2025-12-31"}'
# Returns 403: "Admin access required"

# Admin deletes a coupon
curl -X DELETE "http://127.0.0.1:8000/admin/coupons/SAVE20" \
  -H "X-Admin-Key: admin-secret-key-2024"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Coupon code unique | `if code in coupons: raise 409` | Checked before creation |
| Discount 1–80% | `Field(ge=1, le=80)` | Pydantic boundary — auto 422 |
| Future expiry | `coupon_data.expiry <= date.today()` | Manual check after Pydantic validation |
| Min order value | `coupon["min_order_value"]` comparison | Optional field, checked if not None |
| Expired → controlled error | 400, not 404 | Coupon exists but unusable — user should know |
| Customer cannot create/delete | `require_admin` detects CUSTOMER_KEY → 403 | Valid key but wrong role gets 403, not 401 |
| Admin endpoints under `/admin/` | URL path prefix | Visual role boundary — clear in docs and curl |
| Security() not Depends() | `Security(header)` on params | Registers both schemes in Swagger UI Authorize |
