# E-Commerce Inventory Protection API

A secure FastAPI-based e-commerce inventory system with API key authentication, rate limiting, and thread-safe stock management to prevent overselling.

## Features

- List all products with current stock levels
- Purchase products with quantity validation (1–20)
- API key authentication on purchase endpoint
- Rate limiting (10 purchases per minute)
- Thread-safe stock reduction prevents negative stock
- Returns 409 when stock is insufficient

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
│  │  GET  /products                  No auth      │    │
│  │  POST /products/{id}/purchase    API Key      │    │
│  │                                + 10/min limit │    │
│  └─────────────────────┬────────────────────────┘    │
│                        │                              │
│                        ▼                              │
│  ┌──────────────────────────────────────────────┐    │
│  │             In-Memory Store                   │    │
│  │                                               │    │
│  │  products = {id → {name, price, stock}}      │    │
│  │  threading.Lock protects stock mutations      │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/products` | None | None | List all products |
| POST | `/products/{id}/purchase` | X-API-Key | 10/min | Purchase a product |

## Code Flow Diagram

### POST /products/{product_id}/purchase

```
Client                                   Server
  │                                        │
  │  POST /products/{id}/purchase          │
  │  Headers: X-API-Key                    │
  │  {quantity: 3}                         │
  │ ──────────────────────────────────►    │
  │                                        ├─ Verify API Key (Depends)
  │                                        │   └─ Invalid? → 401
  │                                        ├─ Check rate limit
  │                                        │   └─ Exceeded? → 429
  │                                        ├─ Pydantic validates body
  │                                        │   └─ Invalid? → 422
  │                                        ├─ Lookup product_id in products
  │                                        │   └─ Missing? → 404
  │                                        ├─ Acquire thread lock
  │                                        ├─ Check stock ≥ quantity
  │                                        │   └─ Insufficient? → 409
  │                                        ├─ Reduce stock (thread-safe)
  │                                        ├─ Release thread lock
  │  ◄──────────────────────────────────  │
  │  200 {message, product_id,            │
  │       quantity_purchased,             │
  │       remaining_stock}                │
```

## In-Memory Products

```python
products = {
    1: {"name": "Laptop",   "price": 999.99, "stock": 10},
    2: {"name": "Mouse",    "price": 25.99,  "stock": 50},
    3: {"name": "Keyboard", "price": 49.99,  "stock": 5},
    4: {"name": "Monitor",  "price": 199.99, "stock": 2},
}
```

## Pydantic Models

### PurchaseRequest

```python
class PurchaseRequest(BaseModel):
    quantity: int = Field(ge=1, le=20)   # 1–20 enforced by Pydantic → 422
```

## Auth Strategy

| Header | Env Var | Endpoint | Purpose |
|--------|---------|----------|---------|
| `X-API-Key` | `API_KEY` | `POST /products/{id}/purchase` | Prevents anonymous purchases |

```python
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")

def require_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

## Stock Safety

`threading.Lock` ensures that stock check and reduction happen atomically:

```python
with stock_lock:
    if product["stock"] < quantity:
        raise HTTPException(status_code=409, detail="Insufficient stock")
    product["stock"] -= quantity
```

Without this lock, two concurrent requests could both see `stock=1`, both pass the check, and both reduce — leaving stock at `-1`.

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Successful purchase, product list |
| 401 | Unauthorized | Invalid/missing API key |
| 404 | Not Found | Product ID doesn't exist |
| 409 | Conflict | Insufficient stock |
| 422 | Validation Error | Quantity out of range (1–20) |
| 429 | Too Many Requests | Rate limit exceeded |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic slowapi
```

### 2. Set API key

A `.env` file is provided with a default key. Change it for production:

```
API_KEY=secure-api-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# List products
curl -X GET "http://127.0.0.1:8000/products"

# Purchase 2 laptops
curl -X POST "http://127.0.0.1:8000/products/1/purchase" \
  -H "X-API-Key: secure-api-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'

# Try to buy too many — returns 409
curl -X POST "http://127.0.0.1:8000/products/1/purchase" \
  -H "X-API-Key: secure-api-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 100}'
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Product ID must be positive integer | `product_id: int` in path param | FastAPI auto-validates path type |
| Quantity 1–20 | `quantity: int = Field(ge=1, le=20)` | Pydantic validates at the boundary |
| Insufficient stock returns 409 | `raise HTTPException(status_code=409)` | Conflict — resource exists but can't fulfill |
| Stock never negative | `threading.Lock` around check-and-reduce | Prevents race condition on concurrent requests |
| Rate limit 10/min | `@limiter.limit("10/minute")` | slowapi enforces per-IP |
| Purchase protected by API key | `Depends(require_api_key)` | Guard injected via dependencies |
