# Secure Course Purchase API

A secure FastAPI-based course purchase API for an EdTech platform.

## Features

- Server-side course pricing (price never accepted from client)
- Coupon code validation on the server
- Quantity restriction (1–5)
- API key authentication
- Unique purchase ID generation (UUID)
- Proper HTTP status codes and validation

## Architecture

### Request Flow

```
┌─────────┐       POST /courses/purchase            ┌──────────┐
│         │  ───────────────────────────────────►    │          │
│ Client  │  {email, course_id, qty, coupon_code}   │  Server  │
│         │  ◄───────────────────────────────────   │          │
│         │  201 {purchase_id, final_amount, ...}    │          │
└─────────┘                                         └────┬─────┘
                                                          │
                          ┌────────────────────────────────┼──────────────────────────┐
                          ▼                                ▼                          ▼
                    ┌──────────────┐               ┌──────────────┐          ┌──────────────────┐
                    │   COURSES    │               │   COUPONS    │          │   purchases[]    │
                    │  (dict)      │               │  (dict)      │          │  (in-memory dict)│
                    │              │               │              │          │                  │
                    │  id → {      │               │  code → %    │          │  uuid → {        │
                    │   name,      │               │  EURON20→20  │          │   email, qty,    │
                    │   price      │               │  STUDENT10→10│          │   final_amount,  │
                    │  }           │               │  FLAT50→50   │          │   ...            │
                    └──────────────┘               └──────────────┘          │  }               │
                                                                             └──────────────────┘
```

### Server-Side Data Sources (never from client)

| Data | Source | Why |
|------|--------|-----|
| Course price | `COURSES` dict | Client could send `0` or negative values |
| Discount % | `COUPONS` dict | Client could invent fake codes |
| Purchase ID | `uuid.uuid4()` | Prevents enumeration attacks |
| Final amount | Computed server-side | Client could tamper with calculation |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email]
```

### 2. Set the API key

A `.env` file is provided with a default key. You can change it:

```
API_KEY=your-secret-key-here
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# Purchase a course
curl -X POST "http://127.0.0.1:8000/courses/purchase" \
  -H "X-API-Key: akash-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"student_email": "student@example.com", "course_id": 1, "quantity": 2, "coupon_code": "CASH20"}'

# Get purchase details
curl -X GET "http://127.0.0.1:8000/purchases/{purchase_id}" \
  -H "X-API-Key: akash-secret-key-2024"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/courses/purchase` | Purchase a course (requires API key) |
| GET | `/purchases/{purchase_id}` | Get purchase details (requires API key) |

## Available Courses (server-side)

| ID | Name | Price |
|----|------|-------|
| 1 | Python Masterclass | ₹499 |
| 2 | Machine Learning | ₹799 |
| 3 | Generative AI | ₹999 |
| 4 | Data Science | ₹699 |
| 5 | FastAPI Pro | ₹399 |

## Valid Coupon Codes

| Code | Discount |
|------|----------|
| CASH20 | 20% |
| STUDENT10 | 10% |
| FLAT50 | 50% |
| WELCOME15 | 15% |

## ⚠️ Important Security Pointer: Why Price Must Not Be Trusted from the Frontend

### The core problem

Any data sent from the client (browser, frontend, mobile app) can be manipulated. There is no technical barrier preventing a user from modifying HTTP requests. An attacker can use browser dev tools, `curl`, Postman, or custom scripts to send arbitrary values.

### Attack scenarios if price came from the frontend

| Attack | What attacker sends | Impact |
|--------|---------------------|--------|
| **Zero-price** | `"price": 0` | Gets the course for free |
| **Negative-price** | `"price": -1000` | Server adds money to attacker's account (or deducts from the platform) |
| **Price undercutting** | `"price": 50` (actual is ₹999) | Pays far below market rate |
| **Discount manipulation** | `"discount_percent": 100` | Gets 100% off instead of the allowed 20% |

### Code comparison: BROKEN vs SECURE

```python
# ❌ BROKEN — client sends the price
class BadPurchaseRequest(BaseModel):
    student_email: EmailStr
    course_id: int
    quantity: int
    price: float        # Client controls this — can set to 0 or -1000
    coupon_code: str | None

# ✅ SECURE — server looks up the price
class GoodPurchaseRequest(BaseModel):
    student_email: EmailStr
    course_id: int       # Only an identifier, not the price
    quantity: int
    coupon_code: str | None

# Price comes from server-side authority, not the request body
unit_price = COURSES[request.course_id]["price"]
```

### The principle

> **The server is the single source of truth for any data that has monetary value.**
>
> The frontend sends only identifiers (course_id, quantity, coupon_code). The server computes everything financial (price lookup, discount calculation, final amount). This makes manipulation impossible because the attacker can only control what they send — not what the server looks up internally.

**In one sentence:** *Never trust the client with money — a request is just a string of bytes that anyone can forge.*
