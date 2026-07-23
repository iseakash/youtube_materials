# Banking Money Transfer API

A secure FastAPI-based banking API for transferring money between accounts with rate limiting and API key authentication.

## Features

- Transfer money between bank accounts
- Account numbers validated as 8–18 digit strings
- Amount validation (₹1 – ₹1,00,000)
- Sender and receiver must be different
- Sender must have sufficient balance
- Every transaction gets a unique UUID transaction ID
- API key authentication on all endpoints
- Rate limit: 5 transfers per minute per IP
- Validate-then-mutate pattern (balance updates only after all checks pass)

## Architecture

### Request Flow

```
Client                          Server
  │                               │
  │  POST /accounts/transfer      │
  │  Headers: X-API-Key           │
  │  {from_account: "1001",       │
  │   to_account: "1002",         │
  │   amount: 5000}               │
  │ ──────────────────────────►   │
  │                               ├─ Verify API Key (Security)
  │                               │   └─ Invalid? → 401
  │                               ├─ Rate limit check (5/min per IP)
  │                               │   └─ Exceeded? → 429
  │                               ├─ Validate request body (Pydantic)
  │                               │   └─ Invalid? → 422
  │                               ├─ Check from_account exists
  │                               │   └─ Not found? → 404
  │                               ├─ Check to_account exists
  │                               │   └─ Not found? → 404
  │                               ├─ Check from != to
  │                               │   └─ Same? → 400
  │                               ├─ Check sufficient balance
  │                               │   └─ Insufficient? → 400
  │                               │
  │                               ├─ ✓ ALL VALIDATIONS PASSED
  │                               ├─ Deduct from sender balance
  │                               ├─ Add to receiver balance
  │                               ├─ Generate UUID transaction_id
  │                               ├─ Store transaction record
  │  ◄──────────────────────────  │
  │  200 {transaction_id, msg}    │
```

### Server-Side Data

```python
ACCOUNTS = {
    "1001": {"name": "Alice",   "balance": 50000.0},
    "1002": {"name": "Bob",     "balance": 30000.0},
    "1003": {"name": "Charlie", "balance": 100000.0},
}

transactions = []  # list of completed transaction records
```

## Pydantic Model

```python
class TransferRequest(BaseModel):
    from_account: str = Field(min_length=8, max_length=18, pattern=r"^\d+$")
    to_account: str   = Field(min_length=8, max_length=18, pattern=r"^\d+$")
    amount: float     = Field(gt=0, le=100000)
```

- `from_account` / `to_account` — string of digits, 8–18 characters (validates account number format server-side)
- `amount` — must be greater than 0 and at most ₹1,00,000

## Design Decisions

| Requirement | Implementation | Reasoning |
|---|---|---|
| Amount > 0 & ≤ ₹1,00,000 | `Field(gt=0, le=100000)` | Pydantic validates at the boundary |
| Sender ≠ Receiver | Manual check via `if` | Cross-field validation not possible with single `Field` |
| Sufficient balance | Manual check before mutation | Ensures validate-then-mutate pattern |
| Unique transaction ID | `uuid.uuid4()` | Cryptographically random, no collisions |
| API key protection | `APIKeyHeader` + `Security` | Follows existing `main.py` pattern |
| Rate limit 5/min | slowapi `@limiter.limit("5/minute")` | Per-IP throttling prevents brute-force transfers |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv slowapi
```

### 2. Set the API key

A `.env` file is provided with a default key. Change it for production:

```
API_KEY=euron-banking-secret-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# Transfer money
curl -X POST "http://127.0.0.1:8000/accounts/transfer" \
  -H "X-API-Key: euron-banking-secret-2024" \
  -H "Content-Type: application/json" \
  -d '{"from_account": "1001", "to_account": "1002", "amount": 5000}'

# Check balance
curl -X GET "http://127.0.0.1:8000/accounts/1001/balance" \
  -H "X-API-Key: euron-banking-secret-2024"

# Insufficient balance
curl -X POST "http://127.0.0.1:8000/accounts/transfer" \
  -H "X-API-Key: euron-banking-secret-2024" \
  -H "Content-Type: application/json" \
  -d '{"from_account": "1002", "to_account": "1001", "amount": 999999}'
```

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | `/accounts/transfer` | API Key | 5/min | Transfer money between accounts |
| GET | `/accounts/{account_id}/balance` | API Key | None | Get account balance |
| GET | `/health` | None | None | Health check |

## Validation Order

```
 1. API Key valid?              No → 401
 2. Rate limit exceeded?        Yes → 429
 3. Request body valid?         No → 422 (Pydantic auto)
 4. from_account exists?        No → 404
 5. to_account exists?          No → 404
 6. from ≠ to?                  No → 400
 7. Sufficient balance?         No → 400
 8. ─── ALL PASSED → MUTATE ───
```

## ⚠️ Important Security Pointer: Validate-Then-Mutate

### The core problem

In financial transactions, **order matters**. If balance is updated before all validations complete, a failed check mid-way can leave the system in an inconsistent state.

### Attack scenarios prevented

| Scenario | What happens if balance is mutated early |
|----------|------------------------------------------|
| Sender deducted, but receiver doesn't exist | Money disappears from sender, never reaches anyone |
| Sender deducted, but rate limit exceeded | Transfer rejected but money is gone |
| Sender deducted, then an exception occurs | Money lost with no record |

### How our code prevents this

```python
# ✅ ALL VALIDATIONS FIRST — no mutations
sender = ACCOUNTS.get(transfer_data.from_account)     # check 1
if not sender: raise HTTPException(404)

receiver = ACCOUNTS.get(transfer_data.to_account)     # check 2
if not receiver: raise HTTPException(404)

if transfer_data.from_account == transfer_data.to_account:  # check 3
    raise HTTPException(400)

if sender["balance"] < transfer_data.amount:           # check 4
    raise HTTPException(400)

# ─── GATE: Only reach this point if ALL checks pass ───

sender["balance"] -= transfer_data.amount              # ✅ mutate
receiver["balance"] += transfer_data.amount            # ✅ mutate
```

Because FastAPI processes each request synchronously in a single thread (for standard sync endpoints), the balance mutation is **atomic with respect to the validation block**. There is no window where a partial update can be observed.

### The principle

> **Validate everything you can before you change anything. Never mutate state unless every single check has passed.**
>
> In banking, this is equivalent to a database transaction: all validations are the "read phase," and balance updates are the "write phase." If any validation fails, the write phase is never entered.
