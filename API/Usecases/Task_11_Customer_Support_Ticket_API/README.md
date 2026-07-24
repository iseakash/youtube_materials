# Customer Support Ticket API

A secure FastAPI-based customer support ticket system with role-based authentication (customer & staff keys), priority/status enums, duplicate open ticket prevention, and rate limiting.

## Features

- Create support tickets with email, subject, description, and priority
- Subject: 5–100 characters, Description: 20–2000 characters
- Priority restricted to enum: `low`, `medium`, `high`, `critical`
- Status restricted to enum: `open`, `in_progress`, `resolved`, `closed`
- Prevents duplicate open tickets with the same email and subject
- Staff-only endpoint to update ticket status and add internal notes
- Internal notes are never exposed to customers via GET or POST response
- Rate limit: 5 tickets per hour per IP (via slowapi)
- API key authentication on all endpoints (Security with Swagger UI Authorize)

## Architecture

```
┌──────────────┐
│   Customer   │
└──────┬───────┘
       │  POST /tickets          GET /tickets/{id}
       │  X-Customer-Key         X-Customer-Key
       ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │            Customer-Facing Endpoints              │    │
│  │                                                    │    │
│  │  POST /tickets:                                    │    │
│  │    ├─ Security(require_customer_key)              │    │
│  │    ├─ Pydantic validate body (422)                │    │
│  │    ├─ Rate limit 5/hr (429)                       │    │
│  │    ├─ Duplicate open ticket check (409)           │    │
│  │    └─ Return ticket WITHOUT internal_notes (201)  │    │
│  │                                                    │    │
│  │  GET /tickets/{id}:                                │    │
│  │    ├─ Security(require_customer_key)              │    │
│  │    ├─ Lookup ticket (404)                         │    │
│  │    └─ Return ticket WITHOUT internal_notes (200)  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │            Staff-Only Endpoints                   │    │
│  │                                                    │    │
│  │  PATCH /tickets/{id}:                              │    │
│  │    ├─ Security(require_staff_key)                 │    │
│  │    ├─ Lookup ticket (404)                         │    │
│  │    ├─ Validate status enum (422)                  │    │
│  │    ├─ Update status + notes                       │    │
│  │    ├─ If closed → remove from open index          │    │
│  │    └─ Return full ticket incl. notes (200)        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                    │    │
│  │  tickets = {uuid → {ticket_id, email, subject,    │    │
│  │                     description, priority, status, │    │
│  │                     internal_notes}}               │    │
│  │                                                    │    │
│  │  open_tickets_by_email_subject = {                │    │
│  │    (email, subject): uuid  ← O(1) duplicate check │    │
│  │  }                                                 │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | `/tickets` | X-Customer-Key | 5/hour | Create a new ticket |
| GET | `/tickets/{id}` | X-Customer-Key | None | View a ticket (no internal notes) |
| PATCH | `/tickets/{id}` | X-Staff-Key | None | Update ticket status + add notes |
| GET | `/health` | None | None | Health check |

## Code Flow Diagrams

### POST /tickets — Create Ticket

```
Customer                                  Server
  │                                        │
  │  POST /tickets                         │
  │  Headers: X-Customer-Key               │
  │  Body: {customer_email, subject,       │
  │         description, priority}         │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_customer_key)
  │                                        │  └─ Invalid → 401
  │                                        ├─ Pydantic validates body
  │                                        │  └─ Invalid → 422
  │                                        ├─ slowapi rate limit 5/hour
  │                                        │  └─ Exceeded → 429
  │                                        ├─ (email, subject) in
  │                                        │  open_tickets_by_email_subject?
  │                                        │  └─ Exists → 409
  │                                        │
  │                                        ├─ ✓ ALL VALIDATIONS PASSED
  │                                        ├─ Generate UUID ticket_id
  │                                        ├─ Store ticket with status="open"
  │                                        ├─ Index in open_tickets_by_email_subject
  │                                        │
  │  ◄──────────────────────────────────  │
  │  201 {ticket_id, customer_email,       │
  │       subject, description, priority,  │
  │       status}                          │
  │       (NO internal_notes)              │
```

### GET /tickets/{ticket_id} — View Ticket

```
Customer                                  Server
  │                                        │
  │  GET /tickets/{id}                     │
  │  Headers: X-Customer-Key               │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_customer_key)
  │                                        │  └─ Invalid → 401
  │                                        ├─ Lookup id in tickets dict
  │                                        │  └─ Missing → 404
  │                                        ├─ Strip internal_notes from response
  │  ◄──────────────────────────────────  │
  │  200 {ticket_id, customer_email,       │
  │       subject, description, priority,  │
  │       status}                          │
  │       (NO internal_notes)              │
```

### PATCH /tickets/{ticket_id} — Update Status

```
Staff                                     Server
  │                                        │
  │  PATCH /tickets/{id}                   │
  │  Headers: X-Staff-Key                  │
  │  Body: {status, internal_notes?}       │
  │ ──────────────────────────────────►    │
  │                                        ├─ Security(require_staff_key)
  │                                        │  └─ Invalid → 401
  │                                        ├─ Lookup id in tickets dict
  │                                        │  └─ Missing → 404
  │                                        ├─ Pydantic validates status enum
  │                                        │  └─ Invalid → 422
  │                                        ├─ Update ticket["status"]
  │                                        ├─ Append internal_notes if provided
  │                                        ├─ If status=closed → remove from
  │                                        │  open_tickets_by_email_subject index
  │  ◄──────────────────────────────────  │
  │  200 {ticket_id, customer_email,       │
  │       subject, description, priority,  │
  │       status, internal_notes}          │
  │       (staff sees full data)           │
```

## Pydantic Models

### Priority (enum)

```python
class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
```

Any string not in this list (e.g. `"urgent"`) is rejected by Pydantic with 422.

### TicketStatus (enum)

```python
class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
```

### TicketCreate

```python
class TicketCreate(BaseModel):
    customer_email: EmailStr
    subject: str = Field(min_length=5, max_length=100)
    description: str = Field(min_length=20, max_length=2000)
    priority: Priority
```

### TicketStatusUpdate

```python
class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    internal_notes: str | None = None
```

## Auth Strategy

| Header | Env Var | Endpoint | Purpose |
|--------|---------|----------|---------|
| `X-Customer-Key` | `CUSTOMER_KEY` | POST, GET | Customer access |
| `X-Staff-Key` | `STAFF_KEY` | PATCH | Staff-only status updates |

Using `Security()` instead of `Depends()` registers both schemes in Swagger UI's Authorize dialog.

```python
customer_key_header = APIKeyHeader(name="X-Customer-Key", auto_error=False, scheme_name="customer-key")
staff_key_header = APIKeyHeader(name="X-Staff-Key", auto_error=False, scheme_name="staff-key")

def require_customer_key(key: str = Security(customer_key_header)):
    if key != CUSTOMER_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key

def require_staff_key(key: str = Security(staff_key_header)):
    if key != STAFF_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
```

## Security — Internal Notes Protection

**Internal support notes must never be returned to the customer.**

Both `POST /tickets` (201 response) and `GET /tickets/{id}` (200 response) manually construct the response dict — `internal_notes` is intentionally omitted:

```python
# Customer-facing response — NO internal_notes field
return {
    "ticket_id": ticket["ticket_id"],
    "customer_email": ticket["customer_email"],
    "subject": ticket["subject"],
    "description": ticket["description"],
    "priority": ticket["priority"],
    "status": ticket["status"],
}
```

Only `PATCH /tickets/{id}` (staff-only) returns the full ticket dict including `internal_notes`.

## Duplicate Open Ticket Prevention

```python
# Tuple (email, subject) is hashable → O(1) duplicate lookup
open_tickets_by_email_subject: dict[tuple[str, str], str] = {}

dup_key = (ticket_data.customer_email, ticket_data.subject)
if dup_key in open_tickets_by_email_subject:
    raise HTTPException(status_code=409, detail="...")
```

When a ticket is **closed**, it is removed from this index:

```python
if status_data.status == TicketStatus.closed:
    dup_key = (ticket["customer_email"], ticket["subject"])
    open_tickets_by_email_subject.pop(dup_key, None)
```

This allows the customer to create a new ticket with the same subject after the previous one is closed.

## Rate Limiting

| Endpoint | Limit | Method | Key Function |
|----------|-------|--------|-------------|
| POST `/tickets` | 5/hour | slowapi `@limiter.limit("5/hour")` | `get_remote_address` (IP-based) |

## Duplicate vs Rate Limit vs Auth — Order

```
 1. Security() auth check                → 401
 2. Pydantic body validation             → 422
 3. Rate limit (slowapi)                 → 429
 4. Duplicate open ticket check          → 409
 5. ─── ALL PASS → Store ticket ───          201
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Ticket retrieved / updated |
| 201 | Created | Ticket created |
| 401 | Unauthorized | Invalid/missing customer or staff key |
| 404 | Not Found | Ticket ID doesn't exist |
| 409 | Conflict | Duplicate open ticket (same email + subject) |
| 422 | Validation Error | Pydantic field/type/enum violations |
| 429 | Too Many Requests | Rate limit exceeded (5/hour) |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Set API keys

A `.env` file is provided with default keys. Change them for production:

```
CUSTOMER_KEY=customer-secret-key-2024
STAFF_KEY=staff-secret-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs — both `customer-key` and `staff-key` Authorize fields appear.

### 5. Test via curl

```bash
# Create a ticket
curl -X POST "http://127.0.0.1:8000/tickets" \
  -H "X-Customer-Key: customer-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "user@example.com", "subject": "Payment failed", "description": "My payment was deducted but access was not activated.", "priority": "high"}'

# View ticket (internal_notes NOT returned)
curl -X GET "http://127.0.0.1:8000/tickets/<ticket_id>" \
  -H "X-Customer-Key: customer-secret-key-2024"

# Update ticket status (staff only, can see notes)
curl -X PATCH "http://127.0.0.1:8000/tickets/<ticket_id>" \
  -H "X-Staff-Key: staff-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "internal_notes": "Investigating payment issue with payment gateway"}'

# Try duplicate — returns 409
curl -X POST "http://127.0.0.1:8000/tickets" \
  -H "X-Customer-Key: customer-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "user@example.com", "subject": "Payment failed", "description": "Same issue again", "priority": "high"}'
```

### 6. Error scenario — invalid priority

```bash
curl -X POST "http://127.0.0.1:8000/tickets" \
  -H "X-Customer-Key: customer-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "user@example.com", "subject": "Payment failed", "description": "My payment was deducted but access was not activated.", "priority": "urgent"}'
# Returns 422: "Input should be 'low', 'medium', 'high' or 'critical'"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Subject 5–100 chars | `Field(min_length=5, max_length=100)` | Pydantic boundary validation |
| Description 20–2000 chars | `Field(min_length=20, max_length=2000)` | Prevents huge descriptions |
| Priority enum | `class Priority(str, Enum)` | Auto 422 for invalid values |
| Duplicate open tickets | `open_tickets_by_email_subject` dict | O(1) tuple-keyed lookup |
| Only staff updates status | `Security(require_staff_key)` | Different key header for staff |
| Internal notes hidden | Manually stripped in response | Customers never see notes |
| Rate limit 5/hour per user | slowapi IP-based `5/hour` | Simple, no manual tracker |
| Auth with Swagger UI | `Security()` not `Depends()` | Registers schemes in OpenAPI |
