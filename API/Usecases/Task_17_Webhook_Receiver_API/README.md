# Webhook Receiver API

A secure FastAPI-based webhook endpoint that receives payment status updates from a payment gateway. Prevents replay attacks by rejecting duplicate event IDs.

## Features

- **Webhook secret auth** — requests must contain `X-Webhook-Secret` header
- **Replay attack prevention** — each `event_id` is processed only once; duplicates return immediately
- **Status enum** — only `success`, `failed`, `pending`, `refunded` allowed
- **Positive amount** — validated at the Pydantic boundary
- **Swagger UI Authorize** — webhook secret has a dedicated field

## What is a Webhook?

A webhook is an **HTTP callback** — instead of your API polling the payment gateway for status updates, the payment gateway sends an HTTP POST to your API when an event occurs.

### Polling vs Webhook

**Polling (inefficient) — your API repeatedly asks for updates:**

```
Your API                  Payment Gateway
  │                            │
  │  GET /payment/status?      │
  │  Any update yet?           │
  │ ──────────────────────►    │
  │  ◄── "No, still pending"   │
  │                            │
  │  (repeat every 30 seconds) │
  │                            │
  │  GET /payment/status?      │
  │ ──────────────────────►    │
  │  ◄── "Yes, success!"       │
```

**Webhook (instant) — gateway pushes the update to you:**

```
Your API                  Payment Gateway
  │                            │
  │                            │  Payment completes
  │                            │
  │  ◄── POST /webhooks/   ───│
  │       payment              │
  │       {event_id, status,   │
  │        amount}             │
  │                            │
  │  Return 200                │
```

Webhooks are faster and use fewer server resources — your API doesn't waste time polling when nothing has changed.

### Key Webhook Concepts

| Concept | Meaning | Why It Matters |
|---------|---------|----------------|
| **Webhook Secret** | A shared password between sender and receiver | Proves the request genuinely came from the payment gateway |
| **Payload** | The JSON body containing event data | Tells your API what happened (payment succeeded, failed, etc.) |
| **Event ID** | A unique identifier for each event | Lets your API detect and reject duplicate requests |
| **Idempotency** | Processing the same event multiple times has the same effect as processing it once | Prevents double payments if the gateway retries delivery |
| **Replay Attack** | An attacker re-sends a captured webhook request | Without idempotency, the attacker could trigger double processing |

### Why Webhooks Need Security

Your webhook endpoint (`POST /webhooks/payment`) is a **public URL**. Anyone who discovers it can send fake payment updates — unless you verify the sender.

```
Attacker                          Your API
  │                                    │
  │  POST /webhooks/payment            │
  │  Body: {status: "success",         │
  │         amount: 999999}            │
  │  (No secret header)                │
  │ ──────────────────────────────►    │
  │                                    ├─ Missing secret → 401
  │  ◄──────────────────────────────  │
  │  401 {"detail": "Invalid           │
  │        webhook secret"}            │
```

### How This API Protects Against Each Threat

| Threat | Protection |
|--------|------------|
| Fake webhook from attacker | `X-Webhook-Secret` header validated server-side |
| Replay attack (same event sent twice) | `processed_events` set rejects duplicate `event_id` |
| Invalid status value | `PaymentStatus` enum rejects via 422 |
| Invalid amount (negative/zero) | `Field(gt=0)` rejects via 422 |

## Architecture

```
┌──────────────────────┐
│  Payment Gateway     │
│                      │
│  POST /webhooks/     │
│  payment             │
│  + X-Webhook-Secret  │
│  + event_id (unique) │
│  + payment_id        │
│  + status            │
│  + amount            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  verify_webhook_secret( Security )                    │    │
│  │  ── X-Webhook-Secret via APIKeyHeader                 │    │
│  │                                                       │    │
│  │  1. Missing / wrong secret → 401                      │    │
│  │  2. Valid secret       → proceed                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Replay Protection                                    │    │
│  │                                                       │    │
│  │  processed_events = set()  ← stores event_ids        │    │
│  │                                                       │    │
│  │  if event_id in set:                                  │    │
│  │    return "Event already processed" ← idempotent     │    │
│  │  else:                                                │    │
│  │    add to set + process                               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Pydantic Validation                                  │    │
│  │                                                       │    │
│  │  WebhookPayload:                                       │    │
│  │    event_id: str (min_length=1)                       │    │
│  │    payment_id: str (min_length=1)                     │    │
│  │    status: PaymentStatus (enum)                       │    │
│  │    amount: float (gt=0)                               │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | `/webhooks/payment` | X-Webhook-Secret | Receive a payment status update |

## Auth Strategy

| Header | Env Var | Description |
|--------|---------|-------------|
| `X-Webhook-Secret` | `WEBHOOK_SECRET` | Shared secret between payment gateway and your app |

```python
webhook_header = APIKeyHeader(name="X-Webhook-Secret", auto_error=False)

def verify_webhook_secret(key: str = Security(webhook_header)):
    if key != WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return key
```

## Replay Attack Prevention

A replay attack occurs when an attacker intercepts a valid webhook request and re-sends it to trick the server into processing the same payment twice.

### How this API prevents it

```python
processed_events = set()

@app.post("/webhooks/payment")
def handle_webhook(payload: WebhookPayload, key: str = Security(verify_webhook_secret)):
    if payload.event_id in processed_events:
        return {"message": "Event already processed"}   # Idempotent — same response

    processed_events.add(payload.event_id)              # First time — store and process

    return {
        "message": "Webhook received",
        "event_id": payload.event_id,
        ...
    }
```

- If the same `event_id` arrives again, the API returns immediately **without processing**
- The attacker gains nothing — the payment is not double-processed
- The response is the same whether it's the first or a duplicate (no information leakage)

## Payment Status Enum

```python
class PaymentStatus(str, Enum):
    success = "success"
    failed = "failed"
    pending = "pending"
    refunded = "refunded"
```

Any string not in this list (e.g. `"cancelled"`, `"processing"`) is rejected by Pydantic with **422**.

## Pydantic Models

### WebhookPayload (request body)

```python
class WebhookPayload(BaseModel):
    event_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    status: PaymentStatus
    amount: float = Field(gt=0)
```

| Field | Type | Constraints |
|-------|------|-------------|
| `event_id` | `str` | At least 1 character |
| `payment_id` | `str` | At least 1 character |
| `status` | `PaymentStatus` | Must be one of: success, failed, pending, refunded |
| `amount` | `float` | Must be greater than 0 |

Any field failing constraints → **422 Validation Error**.

## Code Flow Diagrams

### POST /webhooks/payment — First Request (New Event)

```
Payment Gateway                      Server
  │                                    │
  │  POST /webhooks/payment            │
  │  X-Webhook-Secret: whsec_...      │
  │  Body: {event_id: "evt_123",      │
  │         payment_id: "pay_501",    │
  │         status: "success",        │
  │         amount: 2999}             │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(verify_webhook_secret)
  │                                    │  └─ Secret valid? ✓
  │                                    │
  │                                    ├─ Pydantic validate body
  │                                    │  ├─ event_id: str ✓
  │                                    │  ├─ payment_id: str ✓
  │                                    │  ├─ status in enum? ✓
  │                                    │  └─ amount > 0? ✓
  │                                    │
  │                                    ├─ evt_123 in processed_events?
  │                                    │  └─ No → first time
  │                                    │
  │                                    ├─ processed_events.add("evt_123")
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {message: "Webhook received", │
  │       event_id: "evt_123",        │
  │       payment_id: "pay_501",      │
  │       status: "success",          │
  │       amount: 2999}               │
```

### POST /webhooks/payment — Replay Attack (Duplicate Event ID)

```
Attacker (replays intercepted request)   Server
  │                                        │
  │  POST /webhooks/payment               │
  │  X-Webhook-Secret: whsec_...          │
  │  Body: {event_id: "evt_123",          │
  │         payment_id: "pay_501",        │
  │         status: "success",            │
  │         amount: 2999}                 │
  │ ──────────────────────────────────►   │
  │                                        ├─ Security(verify_webhook_secret)
  │                                        │  └─ Secret valid? ✓
  │                                        │
  │                                        ├─ Pydantic validate body ✓
  │                                        │
  │                                        ├─ evt_123 in processed_events?
  │                                        │  └─ YES → already processed
  │                                        │
  │  ◄────────────────────────────────── │
  │  200 {message: "Event already         │
  │        processed"}                    │
  │                                        │
  │    ↑ Attacker gets same response     │
  │      — no double processing          │
```

### POST /webhooks/payment — Invalid Secret

```
Attacker (guessing secret)             Server
  │                                        │
  │  POST /webhooks/payment               │
  │  X-Webhook-Secret: wrong-secret       │
  │  Body: {...valid payload...}          │
  │ ──────────────────────────────────►   │
  │                                        ├─ Security(verify_webhook_secret)
  │                                        │  └── wrong-secret != WEBHOOK_SECRET
  │                                        │
  │  ◄────────────────────────────────── │
  │  401 {"detail": "Invalid webhook      │
  │        secret"}                       │
```

### POST /webhooks/payment — Invalid Status (422)

```
Payment Gateway                      Server
  │                                    │
  │  POST /webhooks/payment            │
  │  Body: {status: "cancelled", ...} │
  │ ──────────────────────────────►   │
  │                                    ├─ Pydantic validate body
  │                                    │  └── "cancelled" not in enum
  │                                    │
  │  ◄────────────────────────────── │
  │  422 {"detail": [...,             │
  │        "Input should be            │
  │         success, failed,           │
  │         pending or refunded"]}     │
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Webhook processed or duplicate acknowledged |
| 401 | Unauthorized | Invalid or missing webhook secret |
| 422 | Validation Error | Invalid status, negative/zero amount, missing fields |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

### 2. Set webhook secret

A `.env` file is provided with a default secret. Change it for production:

```
WEBHOOK_SECRET=whsec_payment_gateway_2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs.

Click the **Authorize** button and enter the webhook secret (`whsec_payment_gateway_2024`). Then try the POST endpoint.

### 5. Test via curl

```bash
# Valid webhook — first request (processed)
curl -X POST "http://127.0.0.1:8000/webhooks/payment" \
  -H "X-Webhook-Secret: whsec_payment_gateway_2024" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_123", "payment_id": "pay_501", "status": "success", "amount": 2999}'

# Duplicate event_id — replay attack prevented
curl -X POST "http://127.0.0.1:8000/webhooks/payment" \
  -H "X-Webhook-Secret: whsec_payment_gateway_2024" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_123", "payment_id": "pay_501", "status": "success", "amount": 2999}'
# → Returns "Event already processed" (no double processing)

# Invalid secret — 401
curl -X POST "http://127.0.0.1:8000/webhooks/payment" \
  -H "X-Webhook-Secret: wrong-secret" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_456", "payment_id": "pay_502", "status": "failed", "amount": 1500}'

# Invalid status — 422
curl -X POST "http://127.0.0.1:8000/webhooks/payment" \
  -H "X-Webhook-Secret: whsec_payment_gateway_2024" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_789", "payment_id": "pay_503", "status": "cancelled", "amount": 2000}'

# Negative amount — 422
curl -X POST "http://127.0.0.1:8000/webhooks/payment" \
  -H "X-Webhook-Secret: whsec_payment_gateway_2024" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_101", "payment_id": "pay_504", "status": "pending", "amount": -500}'
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Webhook secret header | `APIKeyHeader` + `Security()` | Registers in Swagger Authorize; consistent with reference pattern |
| Reject duplicate events | `processed_events` set | O(1) lookup; same response for first vs duplicate (no info leakage) |
| Allowed statuses | `PaymentStatus` enum | Invalid values auto-rejected as 422 by Pydantic |
| Positive amount | `Field(gt=0)` | Pydantic validates before handler runs |
| Return quickly | Early return for duplicates | No processing logic for replayed events |
| Idempotent response | Same 200 for new and duplicate | Attacker cannot distinguish first from replay |
