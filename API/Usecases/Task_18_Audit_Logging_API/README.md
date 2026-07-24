# Audit Logging API

A secure FastAPI-based admin panel that records every sensitive action (create/delete user) in an immutable audit log. The logging function automatically strips sensitive fields like passwords and API keys before storing.

## Features

- **Admin-only endpoints** — all three endpoints require `X-Admin-Key`
- **Automatic audit logging** — every create and delete generates a log entry
- **Sensitive field redaction** — `password`, `api_key`, `secret`, `token` are stripped before logging
- **Immutable logs** — logs are append-only; no update or delete endpoint exists
- **Duplicate email detection** — 409 on duplicate email for user creation
- **Swagger UI Authorize** — admin key has a dedicated field

## Architecture

```
┌─────────────────────┐
│  Admin Client       │
│  + X-Admin-Key      │
└──────────┬──────────┘
           │
           │  POST/DELETE/GET
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  require_admin_key( Security )                        │    │
│  │  ── X-Admin-Key via APIKeyHeader                      │    │
│  │                                                       │    │
│  │  1. Missing / wrong key → 401                         │    │
│  │  2. Valid key → proceed                               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  sanitize(data) — strips sensitive fields             │    │
│  │                                                       │    │
│  │  SENSITIVE_FIELDS = {"password", "api_key",           │    │
│  │                      "secret", "token"}               │    │
│  │                                                       │    │
│  │  Input:  {name, email, password, api_key}             │    │
│  │  Output: {name, email}  ← safe for logging            │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  log_action() — writes to audit_logs list             │    │
│  │                                                       │    │
│  │  {action, admin, timestamp, resource,                 │    │
│  │   result, details (sanitized)}                        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Data Stores                                          │    │
│  │                                                       │    │
│  │  users = [            ← mutable (for CRUD)            │    │
│  │    {id, name, email, password}                        │    │
│  │  ]                                                     │    │
│  │                                                       │    │
│  │  audit_logs = [       ← append-only (immutable)      │    │
│  │    {action, admin, timestamp, resource,               │    │
│  │     result, details}                                  │    │
│  │  ]                                                     │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | `/admin/users` | X-Admin-Key | Create a user (logs: `created`) |
| DELETE | `/admin/users/{user_id}` | X-Admin-Key | Delete a user (logs: `deleted`) |
| GET | `/admin/audit-logs` | X-Admin-Key | View all audit logs |

## Auth Strategy

| Header | Env Var | Description |
|--------|---------|-------------|
| `X-Admin-Key` | `ADMIN_KEY` | Secret key that authorizes admin actions |

The admin identity used in audit logs is set via `ADMIN_IDENTITY` in `.env`.

```python
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def require_admin_key(key: str = Security(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return key
```

## Pydantic Models

### UserCreate (request body for POST)

```python
class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
```

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | `str` | 2–100 characters |
| `email` | `EmailStr` | Valid email format |
| `password` | `str` | At least 6 characters |

Any field failing constraints → **422 Validation Error**.

**Note:** `password` is stored in the `users` list (for login purposes) but is **never** included in audit logs or API responses.

## Security Challenge: Sensitive Field Redaction

The core security challenge is ensuring that sensitive data never leaks into audit logs.

### The `sanitize()` Function

```python
SENSITIVE_FIELDS = {"password", "api_key", "secret", "token"}

def sanitize(data: dict) -> dict:
    return {k: v for k, v in data.items() if k.lower() not in SENSITIVE_FIELDS}
```

This function is called automatically by `log_action()` on every audit entry:

```python
def log_action(action, admin, resource, result, details=None):
    audit_logs.append({
        "action": action,
        "admin": admin,
        "timestamp": ...,
        "resource": resource,
        "result": result,
        "details": sanitize(details) if details else None,  # ← safe
    })
```

### Example: What Gets Logged vs What Doesn't

```
User creates: {"name": "Alice", "email": "alice@corp.com", "password": "s3cret!"}

Stored in users[]:    {id, name, "Alice", email: "alice@corp.com", password: "s3cret!"}
Logged in audit:      {details: {name: "Alice", email: "alice@corp.com"}}
                                                              ↑ password stripped ↑
```

If an attacker gains read access to the audit logs, they see names and emails but **never** passwords or API keys.

### Why Immutable?

Audit logs are stored in an append-only list. There is no endpoint to update or delete log entries. Once written, a log record cannot be modified — this provides a tamper-evident trail of all admin actions.

## Code Flow Diagrams

### POST /admin/users — Create User

```
Admin Client                        Server
  │                                    │
  │  POST /admin/users                 │
  │  X-Admin-Key: <key>               │
  │  Body: {name, email, password}    │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(require_admin_key)
  │                                    │  └─ Key valid? ✓
  │                                    │
  │                                    ├─ Pydantic validate body
  │                                    │  └─ name, email, password ✓
  │                                    │
  │                                    ├─ Duplicate email check
  │                                    │  └─ Not found ✓
  │                                    │
  │                                    ├─ uuid4() → new user
  │                                    │  └─ users.append({...password...})
  │                                    │
  │                                    ├─ log_action("created", admin,
  │                                    │    user_id, "success", new_user)
  │                                    │  └─ sanitize() strips password ✓
  │                                    │
  │  ◄────────────────────────────── │
  │  201 {id, name, email}            │
  │       ↑ password excluded ↑       │
```

### DELETE /admin/users/{user_id} — Delete User

```
Admin Client                        Server
  │                                    │
  │  DELETE /admin/users/uuid-123     │
  │  X-Admin-Key: <key>               │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(require_admin_key) ✓
  │                                    │
  │                                    ├─ Search users for uuid-123
  │                                    │  └─ Found! → pop from list
  │                                    │
  │                                    ├─ log_action("deleted", admin,
  │                                    │    "uuid-123", "success", removed)
  │                                    │  └─ sanitize() strips password ✓
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {message: "User deleted",    │
  │       user_id: "uuid-123"}        │
```

### DELETE — User Not Found

```
Admin Client                        Server
  │                                    │
  │  DELETE /admin/users/wrong-id     │
  │  X-Admin-Key: <key>               │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(require_admin_key) ✓
  │                                    ├─ Search users for wrong-id
  │                                    │  └─ Not found
  │  ◄────────────────────────────── │
  │  404 {"detail": "User not found"} │
```

### GET /admin/audit-logs — View Logs

```
Admin Client                        Server
  │                                    │
  │  GET /admin/audit-logs            │
  │  X-Admin-Key: <key>               │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(require_admin_key) ✓
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {count: 2, logs: [           │
  │    {action: "created",            │
  │     admin: "admin-sarah",         │
  │     timestamp: "2025-...",        │
  │     resource: "uuid-abc",         │
  │     result: "success",            │
  │     details: {name: "Alice",      │
  │               email: "..."}},     │
  │    {action: "deleted", ...}       │
  │  ]}                               │
  │      ↑ No passwords in logs ↑    │
```

## Audit Log Structure

Every audit log entry contains exactly these fields:

```python
{
    "action": "created" | "deleted",
    "admin": "admin-sarah",               # from ADMIN_IDENTITY in .env
    "timestamp": "2025-07-24T14:30:00Z", # UTC — tamper-proof
    "resource": "uuid-abc-...",          # affected user ID
    "result": "success",
    "details": {                         # ← sanitized — no secrets
        "name": "Alice",
        "email": "alice@corp.com"
    }
}
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | User deleted, audit logs retrieved |
| 201 | Created | User created successfully |
| 401 | Unauthorized | Invalid or missing admin key |
| 404 | Not Found | User ID not found for deletion |
| 409 | Conflict | Duplicate email |
| 422 | Validation Error | Invalid name, email, or password format |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email]
```

### 2. Set admin credentials

A `.env` file is provided with defaults:

```
ADMIN_KEY=admin-secret-key-2024
ADMIN_IDENTITY=admin-sarah
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs. Click **Authorize** and enter `admin-secret-key-2024`.

### 5. Test via curl

```bash
# Create a user
curl -X POST "http://127.0.0.1:8000/admin/users" \
  -H "X-Admin-Key: admin-secret-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@corp.com", "password": "s3cret123"}'

# View audit logs (no passwords visible)
curl -X GET "http://127.0.0.1:8000/admin/audit-logs" \
  -H "X-Admin-Key: admin-secret-key-2024"

# Delete a user
curl -X DELETE "http://127.0.0.1:8000/admin/users/<UUID>" \
  -H "X-Admin-Key: admin-secret-key-2024"

# View logs again — deletion logged
curl -X GET "http://127.0.0.1:8000/admin/audit-logs" \
  -H "X-Admin-Key: admin-secret-key-2024"

# Security tests
curl -X GET "http://127.0.0.1:8000/admin/audit-logs"  # No key → 401
curl -X GET "http://127.0.0.1:8000/admin/audit-logs" -H "X-Admin-Key: wrong"  # Wrong key → 401
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| All endpoints require admin key | `APIKeyHeader` + `Security()` | Consistent with reference pattern; Swagger Authorize button |
| Every create/delete generates audit log | `log_action()` called after mutation | Log written only after successful operation |
| Sensitive values not logged | `sanitize()` strips `password`, `api_key`, `secret`, `token` | Automatic — no way to accidentally log a sensitive field |
| Audit logs not modifiable | Append-only `audit_logs` list | No update/delete endpoint for logs |
| Safe error messages | Generic 401 for bad key | No information leakage about valid keys |
| Password not in response | Return dict excludes `password` field | Password is stored but never exposed to client |
