# Multi-Tenant Organization API

A secure FastAPI-based employee management system with **cross-tenant data isolation**. Each organization authenticates with its own API key and can only see its own employees.

## Features

- **Tenant isolation** — employees are scoped by organization
- **Per-org API keys** — each org has a unique key mapped in the server
- **403 on key/org mismatch** — distinct from 401 for unknown orgs
- **Anti-enumeration** — same 404 for missing vs wrong-org employee
- **Pydantic validation** — email format and department length enforced
- **Duplicate email detection** — 409 on duplicate email within the org
- **Swagger UI Authorize** — both `X-Organization-ID` and `X-API-Key` have dedicated fields

## Architecture

```
┌─────────────────────┐      ┌─────────────────────┐
│  Organization Alpha │      │  Organization Beta  │
│  (org-alpha)        │      │  (org-beta)         │
│  Key: key-alpha-... │      │  Key: key-beta-...  │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           │  X-Organization-ID         │  X-Organization-ID
           │  X-API-Key                 │  X-API-Key
           ▼                            ▼
┌───────────────────────────────────────────────────────────────┐
│                    FastAPI Application                         │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  verify_org_access( Security, Security )              │    │
│  │  ── X-Organization-ID via APIKeyHeader (scheme_name)  │    │
│  │  ── X-API-Key         via APIKeyHeader (scheme_name)  │    │
│  │                                                       │    │
│  │  1. Missing headers → 401                             │    │
│  │  2. Unknown org      → 401                            │    │
│  │  3. Wrong key for org → 403                           │    │
│  │  4. Valid             → return org_id                 │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  Route Handlers                                        │    │
│  │                                                         │    │
│  │  POST /employees    → creates employee, checks          │    │
│  │                       duplicate email                   │    │
│  │  GET /employees     → returns only requesting org's     │    │
│  │                       employees                         │    │
│  │  GET /employees/{id} → returns employee only if it      │    │
│  │                         belongs to requesting org       │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  In-Memory Data Store                                  │    │
│  │                                                         │    │
│  │  employees = [                                          │    │
│  │    {id, name, email, department, org_id},               │    │
│  │    {id, name, email, department, org_id},               │    │
│  │  ]                                                       │    │
│  └───────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | `/employees` | X-Organization-ID + X-API-Key | Create an employee under your org |
| GET | `/employees` | X-Organization-ID + X-API-Key | List all employees in your org |
| GET | `/employees/{id}` | X-Organization-ID + X-API-Key | Get a specific employee (yours only) |

## Auth Strategy

Every request requires two headers validated together. Both `APIKeyHeader` instances use unique `scheme_name` so they appear as separate fields in Swagger UI Authorize.

| Header | Env Var | Swagger Scheme |
|--------|---------|----------------|
| `X-Organization-ID` | — (from `ORG_KEYS` dict keys) | `org-id` |
| `X-API-Key` | `ORG_ALPHA_KEY`, `ORG_BETA_KEY` | `api-key` |

### Validation logic

```python
def verify_org_access(
    org_id: str = Security(org_id_header),
    api_key: str = Security(api_key_header),
):
    if not org_id or not api_key:
        raise HTTPException(status_code=401)
    expected_key = ORG_KEYS.get(org_id)
    if expected_key is None:
        raise HTTPException(status_code=401)
    if api_key != expected_key:
        raise HTTPException(status_code=403)
    return org_id
```

### Status codes by scenario

| Scenario | Status | Meaning |
|----------|--------|---------|
| No headers / unknown org | 401 | Invalid credentials |
| Valid org + wrong key | 403 | Key doesn't match org |
| Valid org + correct key | 200/201 | Access granted |

## Cross-Tenant Protection

### 1. Employee creation is scoped

```python
new_employee = {
    "id": str(uuid.uuid4()),       # UUID — non-guessable
    "name": employee.name,
    "email": employee.email,
    "department": employee.department,
    "org_id": org_id,               # ← locked to tenant from auth
}
employees.append(new_employee)
```

### 2. Listing only returns your org's employees

```python
org_employees = [emp for emp in employees if emp["org_id"] == org_id]
```

### 3. Single-employee lookup prevents cross-tenant enumeration

```python
for emp in employees:
    if emp["id"] == employee_id:
        if emp["org_id"] != org_id:
            raise HTTPException(status_code=404, detail="Employee not found")
        return emp
raise HTTPException(status_code=404, detail="Employee not found")
```

Same 404 whether the ID doesn't exist or belongs to another org — attacker cannot distinguish.

## Code Flow Diagrams

### POST /employees — Create Employee

```
Client (org-alpha)                  Server
  │                                    │
  │  POST /employees                   │
  │  X-Organization-ID: org-alpha     │
  │  X-API-Key: key-alpha-2024       │
  │  Body: {name, email, department}  │
  │ ──────────────────────────────►   │
  │                                    ├─ Security(org_id_header)
  │                                    ├─ Security(api_key_header)
  │                                    ├─ org-alpha exists? ✓
  │                                    ├─ key matches? ✓
  │                                    │
  │                                    ├─ Pydantic validate body
  │                                    ├─ Duplicate email? check
  │                                    │
  │                                    ├─ uuid4() ID + store
  │                                    │  └─ org_id = "org-alpha"
  │                                    │
  │  ◄────────────────────────────── │
  │  201 {id, name, email,           │
  │       department, org_id}        │
```

### GET /employees — List (Isolated per Org)

```
Client (org-alpha)                  Server
  │                                    │
  │  GET /employees                    │
  │  X-Organization-ID: org-alpha     │
  │  X-API-Key: key-alpha-2024       │
  │ ──────────────────────────────►   │
  │                                    ├─ verify_org_access → "org-alpha"
  │                                    ├─ Filter employees by org_id
  │  ◄────────────────────────────── │
  │  200 {count: N, employees: [...]} │
```

### GET /employees/{id} — Anti-Enumeration

```
Client (org-alpha) tries ID from org-beta
  │                                    Server
  │  GET /employees/abc-123           │
  │  X-Organization-ID: org-alpha     │
  │ ──────────────────────────────►   │
  │                                    ├─ verify_org_access → "org-alpha"
  │                                    ├─ Found, but org_id != "org-alpha"
  │                                    │  └─ Treat as not found
  │  ◄────────────────────────────── │
  │  404 {"detail": "Employee         │
  │        not found"}                │
  │                                    │
  │    ↑ Same response as truly      │
  │      missing ID                  │
```

## Pydantic Models

### EmployeeCreate (request body)

```python
class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(min_length=2, max_length=100)
```

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | `str` | 2–100 characters |
| `email` | `EmailStr` | Valid email format |
| `department` | `str` | 2–100 characters |

Failed constraints → **422 Validation Error**.

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Employees listed or retrieved |
| 201 | Created | Employee created successfully |
| 401 | Unauthorized | Missing/invalid org credentials |
| 403 | Forbidden | Org ID and API key don't match |
| 404 | Not Found | Employee ID not found or belongs to another org |
| 409 | Conflict | Duplicate email within the org |
| 422 | Validation Error | Invalid email, name, or department format |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email]
```

### 2. Set API keys

A `.env` file is provided with default keys:

```
ORG_ALPHA_KEY=key-alpha-2024
ORG_BETA_KEY=key-beta-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs.

Click the **Authorize** button — you'll see two fields:
- `org-id`: enter `org-alpha` (the organization ID)
- `api-key`: enter `key-alpha-2024` (the matching API key)

Then try the endpoints directly from Swagger UI.

### 5. Test via curl

```bash
# --- Organization Alpha ---

curl -X POST "http://127.0.0.1:8000/employees" \
  -H "X-Organization-ID: org-alpha" \
  -H "X-API-Key: key-alpha-2024" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@alpha.com", "department": "Engineering"}'

curl -X GET "http://127.0.0.1:8000/employees" \
  -H "X-Organization-ID: org-alpha" \
  -H "X-API-Key: key-alpha-2024"

curl -X GET "http://127.0.0.1:8000/employees/<UUID>" \
  -H "X-Organization-ID: org-alpha" \
  -H "X-API-Key: key-alpha-2024"

# --- Security tests ---

# Missing headers → 401
curl -X GET "http://127.0.0.1:8000/employees"

# Wrong key for org → 403
curl -X GET "http://127.0.0.1:8000/employees" \
  -H "X-Organization-ID: org-alpha" \
  -H "X-API-Key: key-beta-2024"

# Invalid email → 422
curl -X POST "http://127.0.0.1:8000/employees" \
  -H "X-Organization-ID: org-alpha" \
  -H "X-API-Key: key-alpha-2024" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "not-email", "department": "Engineering"}'
```

## Pre-loaded Organizations

```python
ORG_KEYS = {
    "org-alpha": os.getenv("ORG_ALPHA_KEY"),
    "org-beta": os.getenv("ORG_BETA_KEY"),
}
```

## Security Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Two-header auth | `APIKeyHeader` with unique `scheme_name` | Both headers appear in Swagger Authorize |
| 403 for key/org mismatch | Explicit check after org lookup | Distinguishes unknown org (401) from wrong key (403) |
| Anti-enumeration | Same 404 for missing vs wrong-org employee | Attacker learns nothing about other tenants |
| Employee scoped at creation | `org_id` set server-side from auth | Client cannot forge org ownership |
| Duplicate email check | Loop over `employees` list | Prevents duplicate accounts per org |
| UUID employee IDs | `uuid.uuid4()` | Non-guessable, no sequential enumeration |
| Pydantic boundary | `Field()` + `EmailStr` | Invalid data rejected before processing |
