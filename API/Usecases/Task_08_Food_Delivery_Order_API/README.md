# Food Delivery Order API

A secure FastAPI-based food delivery order management system with role-based authentication (user & admin keys), restaurant menu validation, and enum-enforced order status.

## Features

- Place an order with multiple items from a restaurant
- View order details (requires user API key)
- Update order status (requires admin API key)
- Order must contain at least one item
- Each item quantity limited to 1–10
- Restaurant must exist
- All items must belong to the selected restaurant
- Status values restricted to a strict enum (`placed`, `accepted`, `preparing`, `out_for_delivery`, `delivered`, `cancelled`)
- Rate limiting on order placement to prevent abuse

## Architecture

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │  HTTP
       ▼
┌──────────────────────────────────────────────────────┐
│                FastAPI Application                    │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │          Route Handlers & Auth Layer          │    │
│  │                                               │    │
│  │  POST /orders            No auth, 10/min      │    │
│  │  GET  /orders/{id}       User Key (Depends)   │    │
│  │  PATCH /orders/{id}/stat  Admin Key (Depends)  │    │
│  └─────────────────────┬────────────────────────┘    │
│                        │                              │
│                        ▼                              │
│  ┌──────────────────────────────────────────────┐    │
│  │             In-Memory Store                   │    │
│  │                                               │    │
│  │  RESTAURANTS = {id → {name, menu}}            │    │
│  │  orders = {uuid → full_order_data}            │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | `/orders` | None | 10/min | Place a new order |
| GET | `/orders/{id}` | User Key | None | View order details |
| PATCH | `/orders/{id}/status` | Admin Key | None | Update order status |
| GET | `/health` | None | None | Health check |

## Code Flow Diagrams

### POST /orders — Place Order

```
Client                                   Server
  │                                        │
  │  POST /orders                          │
  │  {customer_email, restaurant_id,       │
  │   items: [{item_id, quantity}, ...]}   │
  │ ──────────────────────────────────►    │
  │                                        ├─ Pydantic validates body
  │                                        │   └─ Invalid? → 422
  │                                        ├─ Check restaurant_id in RESTAURANTS
  │                                        │   └─ Missing? → 404
  │                                        ├─ For each item in items:
  │                                        │     check item_id in restaurant menu
  │                                        │     └─ Unknown item? → 400
  │                                        │
  │                                        ├─ ✓ ALL VALIDATIONS PASSED
  │                                        ├─ Resolve item names & prices from menu
  │                                        ├─ Generate UUID order_id
  │                                        ├─ Store order with status="placed"
  │  ◄──────────────────────────────────  │
  │  201 {order_id, message}              │
```

### GET /orders/{order_id} — View Order

```
Client                                   Server
  │                                        │
  │  GET /orders/{id}                      │
  │  Headers: X-User-Key                   │
  │ ──────────────────────────────────►    │
  │                                        ├─ Verify User Key (Depends)
  │                                        │   └─ Invalid? → 401
  │                                        ├─ Lookup id in orders
  │                                        │   └─ Missing? → 404
  │  ◄──────────────────────────────────  │
  │  200 {full order data}                │
```

### PATCH /orders/{order_id}/status — Update Status

```
Client                                   Server
  │                                        │
  │  PATCH /orders/{id}/status             │
  │  Headers: X-Admin-Key                  │
  │  {status: "accepted"}                  │
  │ ──────────────────────────────────►    │
  │                                        ├─ Verify Admin Key (Depends)
  │                                        │   └─ Invalid? → 401
  │                                        ├─ Lookup id in orders
  │                                        │   └─ Missing? → 404
  │                                        ├─ Pydantic validates status via Enum
  │                                        │   └─ Invalid value? → 422
  │                                        ├─ Update order["status"]
  │  ◄──────────────────────────────────  │
  │  200 {order_id, new_status, message}   │
```

## Server-Side Data

### RESTAURANTS (hardcoded lookup)

```python
RESTAURANTS = {
    1: {"name": "Pizza Palace",
        "menu": {101: {"name": "Margherita",       "price": 12.99},
                 102: {"name": "Pepperoni",        "price": 14.99},
                 103: {"name": "Farmhouse",        "price": 15.99}}},
    2: {"name": "Burger Barn",
        "menu": {201: {"name": "Classic Burger",   "price": 9.99},
                 202: {"name": "Cheese Burger",    "price": 10.99},
                 203: {"name": "Veggie Burger",    "price": 8.99}}},
    3: {"name": "Sushi Spot",
        "menu": {301: {"name": "California Roll",  "price": 15.99},
                 302: {"name": "Salmon Nigiri",    "price": 18.99},
                 303: {"name": "Dragon Roll",      "price": 21.99}}},
}
```

### orders (in-memory dict, keyed by UUID)

```python
orders = {
    "a1b2c3d4-...": {
        "order_id": "a1b2c3d4-...",
        "customer_email": "anita@example.com",
        "restaurant_id": 1,
        "restaurant_name": "Pizza Palace",
        "items": [
            {"item_id": 101, "name": "Margherita", "price": 12.99, "quantity": 2},
            {"item_id": 102, "name": "Pepperoni",  "price": 14.99, "quantity": 1},
        ],
        "status": "placed",
    }
}
```

## Pydantic Models

### OrderStatus (enum)

```python
class OrderStatus(str, Enum):
    placed = "placed"
    accepted = "accepted"
    preparing = "preparing"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
```

Any string not in this list (e.g. `"shipped"`, `"pending"`) is rejected by Pydantic with 422.

### OrderItem

```python
class OrderItem(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=10)    # 1–10 enforced by Pydantic
```

### OrderCreate

```python
class OrderCreate(BaseModel):
    customer_email: EmailStr              # validates email format
    restaurant_id: int
    items: list[OrderItem] = Field(min_length=1)  # at least 1 item
```

### StatusUpdate

```python
class StatusUpdate(BaseModel):
    status: OrderStatus                   # only enum values allowed
```

## Auth Strategy

| Header | Env Var | Endpoint | Purpose |
|--------|---------|----------|---------|
| `X-User-Key` | `USER_KEY` | `GET /orders/{id}` | Customer access — prevents anonymous snooping |
| `X-Admin-Key` | `ADMIN_KEY` | `PATCH /orders/{id}/status` | Admin-only status changes |

### Implementation

```python
user_key_header = APIKeyHeader(name="X-User-Key", auto_error=False, scheme_name="user-key")
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False, scheme_name="admin-key")

def require_user_key(key: str = Depends(user_key_header)):
    if key != USER_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key

def require_admin_key(key: str = Depends(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
```

## Validation Order (POST /orders)

```
 1. Request body valid per Pydantic?           No → 422
 2. Restaurant ID exists?                       No → 404
 3. Each item_id exists in restaurant's menu?   No → 400
 4. ─── ALL PASSED → Store order ───                201
```

## Server-Side Authority Principle

| Client sends | Server uses |
|---|---|
| `restaurant_id` | Server looks up restaurant name + menu from its own `RESTAURANTS` dict |
| `item_id` | Server resolves item name + price from menu — client-provided names/prices are never trusted |
| `items[].quantity` | Server validates `ge=1, le=10` via Pydantic |

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Success (GET, PATCH) |
| 201 | Created | Order placed |
| 400 | Bad Request | Item not in restaurant's menu |
| 401 | Unauthorized | Invalid/missing user or admin key |
| 404 | Not Found | Restaurant or order not found |
| 422 | Validation Error | Pydantic field/type/enum violations |
| 429 | Too Many Requests | Rate limit exceeded |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Set API keys

A `.env` file is provided with default keys. Change them for production:

```
USER_KEY=user-secret-key-2024
ADMIN_KEY=admin-secret-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# Place an order
curl -X POST "http://127.0.0.1:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "anita@example.com", "restaurant_id": 1, "items": [{"item_id": 101, "quantity": 2}, {"item_id": 102, "quantity": 1}]}'

# View order (requires user key)
curl -X GET "http://127.0.0.1:8000/orders/<order_id>" \
  -H "X-User-Key: user-secret-key-2024"

# Update order status (requires admin key)
curl -X PATCH "http://127.0.0.1:8000/orders/<order_id>/status" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'

# Try invalid enum value — returns 422
curl -X PATCH "http://127.0.0.1:8000/orders/<order_id>/status" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped"}'
```

### 6. Error scenario — item not in restaurant

```bash
curl -X POST "http://127.0.0.1:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "anita@example.com", "restaurant_id": 1, "items": [{"item_id": 999, "quantity": 1}]}'
# Returns 400: "Item 999 does not belong to Pizza Palace"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|---|---|---|
| At least one item | `list[OrderItem] = Field(min_length=1)` | Pydantic enforces at the boundary |
| Quantity 1–10 | `quantity: int = Field(ge=1, le=10)` | Pydantic validates each item |
| Restaurant must exist | Lookup in `RESTAURANTS` dict | Server-authoritative lookup |
| Items belong to restaurant | Cross-check each `item_id` against `restaurant["menu"]` | Prevents fake item IDs |
| Customer views own order | `GET /orders/{id}` with user key auth | No list-all endpoint; UUID prevents enumeration |
| Admin changes status | `PATCH /orders/{id}/status` with admin key | `Depends(require_admin_key)` injected |
| Invalid status prevention | `class OrderStatus(str, Enum)` | Invalid strings auto-rejected as 422 |
| Role-based auth | Separate `USER_KEY` / `ADMIN_KEY` headers | Same pattern as `main.py` |
| Rate limit on POST | slowapi `@limiter.limit("10/minute")` | Prevents abuse of order placement |

## Comparison of `main.py` and `main1.py`

Two working files showcasing different auth approaches. Run any with `uvicorn <file>:app --reload`.

| File | Guard Function Default | Endpoint Auth | Swagger UI Authorize |
|------|----------------------|--------------|---------------------|
| `main.py` | `Depends(header)` | `dependencies=[Depends(guard)]` | No fields (auth hidden from UI) |
| `main1.py` | `Security(header)` | `key = Security(guard)` on endpoint param | Both `user-key` and `admin-key` fields appear |

### `Depends` vs `Security`

| Aspect | `Depends` | `Security` |
|--------|-----------|------------|
| What it does | Calls a function and injects its return value | Same as `Depends`, **plus** registers the scheme in OpenAPI's `securitySchemes` |
| OpenAPI effect | No trace in the spec | Adds entry to `components/securitySchemes` linked to the endpoint |
| Swagger UI | No Authorize button | Authorize button with a fillable field for the key |
| Use when | Auth via curl/headers, no Swagger UI needed | You want key fields to appear in Swagger UI's Authorize dialog |

**`Security()` = `Depends()` with OpenAPI registration side-effect.**

### Important — `scheme_name` for multiple auth schemes

Both files set unique `scheme_name` on each `APIKeyHeader`:

```python
user_key_header = APIKeyHeader(name="X-User-Key", scheme_name="user-key")
admin_key_header = APIKeyHeader(name="X-Admin-Key", scheme_name="admin-key")
```

Without this, both would default to `"APIKeyHeader"` and the second scheme would overwrite the first in the OpenAPI spec.

### Which file to use

| If you... | Use |
|-----------|-----|
| Test via curl / Postman only | `main.py` — simpler, no OpenAPI clutter |
| Want Swagger UI Authorize fields | `main1.py` — `Security()` registers schemes in the spec |
