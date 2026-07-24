# Hospital Appointment Booking API

A secure FastAPI-based hospital appointment booking system with 15-minute slot gap enforcement and API key protection for cancellations.

## Features

- Book an appointment with a doctor on a specific date and time slot
- Retrieve appointment details by ID (only your own data)
- Cancel an appointment (requires API key)
- Past dates are rejected
- Doctor must exist in the system
- Same doctor cannot have two appointments within 15 minutes on the same date
- Patient email validated via Pydantic `EmailStr`
- Rate limiting on booking to prevent abuse (10/min per IP)

## Architecture

```
┌──────────────┐
│   Client     │
│ (Swagger UI) │
└──────┬───────┘
       │  HTTP
       ▼
┌──────────────────────────────────────────────────┐
│              FastAPI Application                  │
│                                                   │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │   Pydantic Body   │  │   APIKeyHeader       │  │
│  │   Validation      │  │   (for DELETE only)  │  │
│  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                        │              │
│           ▼                        ▼              │
│  ┌──────────────────────────────────────────┐    │
│  │         Route Handlers                   │    │
│  │  POST   /appointments      → create()    │    │
│  │  GET    /appointments/{id} → read()      │    │
│  │  DELETE /appointments/{id} → cancel()    │    │
│  └──────────────────┬───────────────────────┘    │
│                     │                             │
│                     ▼                             │
│  ┌──────────────────────────────────────────┐    │
│  │       In-Memory Data Store               │    │
│  │  DOCTORS = {                             │    │
│  │    15: {"name": "Dr. Sharma", ...},      │    │
│  │    21: {"name": "Dr. Patel",  ...},      │    │
│  │    32: {"name": "Dr. Verma",  ...}       │    │
│  │  }                                       │    │
│  │  appointments = {                        │    │
│  │    "uuid-1": { full appointment data },  │    │
│  │    "uuid-2": { ... }                     │    │
│  │  }                                       │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | `/appointments` | None | 10/min | Book a new appointment |
| GET | `/appointments/{id}` | None | None | Get appointment details |
| DELETE | `/appointments/{id}` | API Key | None | Cancel an appointment |
| GET | `/health` | None | None | Health check |

## Code Flow Diagrams

### POST /appointments — Create Appointment

```
Client                                   Server
  │                                        │
  │  POST /appointments                    │
  │  {patient_name, patient_email,         │
  │   doctor_id, appointment_date,         │
  │   time_slot}                           │
  │ ──────────────────────────────────►    │
  │                                        ├─ Pydantic validates body
  │                                        │   └─ Invalid? → 422
  │                                        ├─ Parse date: "2026-07-25" → date
  │                                        │   └─ Past? → 400
  │                                        ├─ Lookup doctor_id in DOCTORS
  │                                        │   └─ Missing? → 404
  │                                        ├─ Parse time_slot "10:30" → 630 min
  │                                        ├─ For each existing appointment
  │                                        │   matching same doctor_id + date:
  │                                        │     compute |existing_min - new_min|
  │                                        │     └─ < 15? → 409
  │                                        │
  │                                        ├─ ✓ ALL VALIDATIONS PASSED
  │                                        ├─ Generate UUID appointment_id
  │                                        ├─ Store appointment in dict
  │  ◄──────────────────────────────────  │
  │  201 {appointment_id, message}         │
```

### GET /appointments/{appointment_id} — Read Appointment

```
Client                                   Server
  │                                        │
  │  GET /appointments/{id}                │
  │ ──────────────────────────────────►    │
  │                                        ├─ Lookup id in appointments
  │                                        │   └─ Missing? → 404
  │  ◄──────────────────────────────────  │
  │  200 {full appointment data}           │
```

### DELETE /appointments/{appointment_id} — Cancel Appointment

```
Client                                   Server
  │                                        │
  │  DELETE /appointments/{id}             │
  │  Headers: X-API-Key                    │
  │ ──────────────────────────────────►    │
  │                                        ├─ Verify API Key (Security)
  │                                        │   └─ Invalid? → 401
  │                                        ├─ Lookup id in appointments
  │                                        │   └─ Missing? → 404
  │                                        ├─ Remove from dict
  │  ◄──────────────────────────────────  │
  │  200 {message: "Appointment cancelled"}│
```

## Server-Side Data

### DOCTORS (hardcoded lookup — server is single source of truth)

```python
DOCTORS = {
    15: {"name": "Dr. Sharma",    "specialty": "Cardiologist"},
    21: {"name": "Dr. Patel",     "specialty": "Dermatologist"},
    32: {"name": "Dr. Verma",     "specialty": "Neurologist"},
}
```

### appointments (in-memory dict, keyed by UUID)

```python
appointments = {
    "a1b2c3d4-...": {
        "appointment_id": "a1b2c3d4-...",
        "patient_name": "Anita Sharma",
        "patient_email": "anita@example.com",
        "doctor_id": 15,
        "doctor_name": "Dr. Sharma",
        "specialty": "Cardiologist",
        "appointment_date": "2026-07-25",
        "time_slot": "10:30"
    }
}
```

## Pydantic Model

```python
class AppointmentCreate(BaseModel):
    patient_name: str           = Field(min_length=2, max_length=100)
    patient_email: EmailStr
    doctor_id: int
    appointment_date: str       = Field(min_length=10, max_length=10)  # "YYYY-MM-DD"
    time_slot: str              = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")  # "HH:MM"
```

## 15-Minute Slot Gap Logic

For the same `doctor_id` + same `appointment_date`:

1. Convert each `time_slot` string `"HH:MM"` → total minutes = `HH * 60 + MM`
2. New request's minutes = `new_min`
3. For each existing appointment, compute `abs(existing_min - new_min)`
4. If any difference **< 15** → block with **409 Conflict**

| Existing Slot | Requested Slot | Gap (min) | Result |
|:---:|:---:|:---:|:---:|
| 10:00 | 10:10 | 10 | ❌ 409 |
| 10:00 | 10:14 | 14 | ❌ 409 |
| 10:00 | 10:15 | 15 | ✅ Allowed |
| 10:00 | 09:46 | 14 | ❌ 409 |
| 10:00 | 09:45 | 15 | ✅ Allowed |

## Validation Order (POST /appointments)

```
 1. Request body valid per Pydantic?        No → 422
 2. Appointment date NOT in the past?        No → 400
 3. Doctor exists?                           No → 404
 4. No overlapping slot (±15 min) for       No → 409
    same doctor + same date?
 5. ─── ALL PASSED → Create appointment ───     201
```

## Security Design

### Principle: Server-Side Authority

The server is the single source of truth. The client sends only:
- `doctor_id` — server looks up doctor name and specialty from its own `DOCTORS` dict
- All other fields validated server-side via Pydantic

### What is NOT exposed

- There is **no list-all-appointments** endpoint — each GET returns only the appointment for the requested ID
- Appointment data cannot be enumerated sequentially (UUIDs are non-guessable)
- DELETE is the only protected endpoint — the API key is required to cancel

### Generic Error Messages

| Scenario | Error |
|----------|-------|
| Invalid API key | "Invalid or missing API key" |
| Appointment not found | "Appointment not found" |

### Validate-Then-Mutate Pattern

```python
# Step 1: ALL validations — no state changes
appointment_date = parse_date(...)           # may raise 400
doctor = DOCTORS.get(doctor_id)              # may raise 404
check_slot_available(...)                    # may raise 409

# Step 2: ONLY THEN mutate state
appointments[appointment_id] = {...}         # ✅ single write
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Success (GET, DELETE) |
| 201 | Created | Appointment booked |
| 400 | Bad Request | Past date, invalid format |
| 401 | Unauthorized | Invalid/missing API key |
| 404 | Not Found | Doctor or appointment not found |
| 409 | Conflict | Slot already booked |
| 422 | Validation Error | Pydantic field/type violations |
| 429 | Too Many Requests | Rate limit exceeded |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Set the API key

A `.env` file is provided with a default key. Change it for production:

```
API_KEY=hospital-secret-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs

### 5. Test via curl

```bash
# Book an appointment
curl -X POST "http://127.0.0.1:8000/appointments" \
  -H "Content-Type: application/json" \
  -d '{"patient_name": "Anita Sharma", "patient_email": "anita@example.com", "doctor_id": 15, "appointment_date": "2026-07-25", "time_slot": "10:30"}'

# Get appointment details
curl -X GET "http://127.0.0.1:8000/appointments/<appointment_id>"

# Cancel appointment (requires API key)
curl -X DELETE "http://127.0.0.1:8000/appointments/<appointment_id>" \
  -H "X-API-Key: hospital-secret-key-2024"
```

### 6. Conflict test — 15-minute gap

```bash
# First booking — succeeds
curl -X POST "http://127.0.0.1:8000/appointments" \
  -H "Content-Type: application/json" \
  -d '{"patient_name": "Anita Sharma", "patient_email": "anita@example.com", "doctor_id": 15, "appointment_date": "2026-07-25", "time_slot": "10:00"}'

# Second booking 10 minutes later — fails with 409
curl -X POST "http://127.0.0.1:8000/appointments" \
  -H "Content-Type: application/json" \
  -d '{"patient_name": "Rahul Singh", "patient_email": "rahul@example.com", "doctor_id": 15, "appointment_date": "2026-07-25", "time_slot": "10:10"}'
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Past dates rejected | `datetime.strptime` + compare with `date.today()` | Server-authoritative date check |
| Doctor must exist | Lookup in `DOCTORS` dict | Hardcoded list; client only sends ID |
| 15-min slot gap | Convert time to minutes, check `abs(diff) < 15` | Prevents double-booking near-overlapping slots |
| Valid email | `EmailStr` | Pydantic validates format at boundary |
| Cancel requires API key | `APIKeyHeader` + `Security` | Protects destructive operation |
| No data exposure | No list endpoint, UUID keys | Only the requesting patient's data is returned |
| Rate limit | slowapi `@limiter.limit("10/minute")` | Prevents brute-force booking attempts |
