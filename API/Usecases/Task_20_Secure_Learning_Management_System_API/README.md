# Complete Secure Learning Management System API

A secure FastAPI-based Learning Management System with three roles (student, instructor, admin), token-based authentication, rate limiting, CORS, and audit logging.

## Features

- **Three roles** — student, instructor, admin with distinct permissions
- **Token-based auth** — login returns a session token; all protected endpoints require `X-Auth-Token`
- **Rate limiting** — login endpoint limited to 5 attempts/minute per IP
- **CORS** — whitelisted frontend origins only
- **Audit logging** — course creation and deletion logged immutably
- **Pydantic validation** — email format, string lengths, seat counts enforced
- **Safe error messages** — no stack traces, no information leakage
- **Pre-seeded accounts** — admin, instructor, and student ready to use

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Clients / Frontends                       │
│  http://localhost:3000          http://localhost:5137           │
└────────────────────────────────┬────────────────────────────────┘
                                 │ CORS whitelist
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  CORS Middleware                          │    │
│  │  Allows: localhost:3000, localhost:5137                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Rate Limiter (slowapi)                      │    │
│  │  POST /auth/login → 5/min per IP                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  PUBLIC      │  │  TOKEN-AUTH      │  │  ADMIN-ONLY      │  │
│  │              │  │                  │  │                  │  │
│  │  POST /auth/ │  │  POST /courses   │  │  DELETE /courses │  │
│  │    login     │  │  POST /courses/  │  │    /{id}         │  │
│  │  POST /      │  │    {id}/enroll   │  │  GET /admin/     │  │
│  │  students/   │  │  POST /courses/  │  │    audit-logs    │  │
│  │  register    │  │    {id}/lessons  │  │                  │  │
│  │  GET /courses│  │  GET /students/  │  │                  │  │
│  │  GET /courses│  │    {id}/courses  │  │                  │  │
│  │    /{id}     │  │                  │  │                  │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Role Guards                                             │    │
│  │                                                           │    │
│  │  get_current_user → require_student                      │    │
│  │                   → require_course_creator (instr/admin)  │    │
│  │                   → require_lesson_creator (instr only)   │    │
│  │                   → require_admin                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  In-Memory Data Stores                                   │    │
│  │                                                           │    │
│  │  users → [ {id, name, email, password, role} ]           │    │
│  │  tokens → { token_str: user_id }                         │    │
│  │  courses → { course_id: {title, description, ...} }      │    │
│  │  enrollments → { course_id: [student_id, ...] }          │    │
│  │  lessons → { course_id: [{id, title, content}, ...] }    │    │
│  │  audit_logs → [ {action, admin, timestamp, ...} ]        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Pre-seeded Accounts

| Role | Email | Password | User ID |
|------|-------|----------|---------|
| Admin | `admin@lms.com` | `admin123` | `user-admin` |
| Instructor | `instructor@lms.com` | `instr123` | `user-instr` |
| Student | `student@lms.com` | `stud123` | `user-stud` |

## API Endpoints

| # | Method | Path | Auth | Role | Rate Limited | Audit Log |
|---|--------|------|------|------|-------------|-----------|
| 1 | POST | `/auth/login` | No | — | 5/min | No |
| 2 | POST | `/students/register` | No | — | No | No |
| 3 | POST | `/courses` | Token | Instructor/Admin | No | Yes |
| 4 | GET | `/courses` | No | Public | No | No |
| 5 | GET | `/courses/{course_id}` | No | Public | No | No |
| 6 | POST | `/courses/{course_id}/enroll` | Token | Student only | No | No |
| 7 | GET | `/students/{student_id}/courses` | Token | Self only | No | No |
| 8 | POST | `/courses/{course_id}/lessons` | Token | Instructor only | No | No |
| 9 | DELETE | `/courses/{course_id}` | Token | Admin only | No | Yes |
| 10 | GET | `/admin/audit-logs` | Token | Admin only | No | No |

## Role Hierarchy

```
                    ┌──────────────────┐
                    │      Admin       │
                    │  (full access)   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Instructor     │
                    │  create courses  │
                    │  create lessons  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │     Student      │
                    │  enroll courses  │
                    │  view own courses│
                    └──────────────────┘
```

### Permissions Matrix

| Action | Student | Instructor | Admin |
|--------|---------|------------|-------|
| View course list | ✓ | ✓ | ✓ |
| View course details | ✓ | ✓ | ✓ |
| Register | ✓ | — | — |
| Login | ✓ | ✓ | ✓ |
| Enroll in course | ✓ | ✗ | ✗ |
| View own enrolled courses | ✓ | — | — |
| Create courses | ✗ | ✓ | ✓ |
| Create lessons | ✗ | ✓ | ✗ |
| Delete courses | ✗ | ✗ | ✓ |
| View audit logs | ✗ | ✗ | ✓ |

## Auth Flow

```
Client                              Server
  │                                    │
  │  POST /auth/login                  │
  │  Body: {email, password}          │
  │ ──────────────────────────────►   │
  │                                    ├─ Rate limit check (5/min)
  │                                    ├─ Validate credentials
  │                                    ├─ Generate token (secrets.token_urlsafe)
  │                                    ├─ Store: tokens[token] = user_id
  │  ◄────────────────────────────── │
  │  200 {token: "abc123...",         │
  │       user_id: "user-stud",       │
  │       role: "student"}            │
  │                                    │
  │  POST /courses/book-1/enroll      │
  │  X-Auth-Token: abc123...         │
  │ ──────────────────────────────►   │
  │                                    ├─ get_current_user → lookup token
  │                                    ├─ require_student → check role
  │                                    ├─ Business validations
  │  ◄────────────────────────────── │
  │  200 {message: "Enrolled"}        │
```

## Testing Scenarios (15 Required)

### 1. Successful Student Registration

```bash
curl -X POST "http://127.0.0.1:8000/students/register" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Student", "email": "new@example.com", "password": "pass123"}'
```
→ **201** `{id, name, email, role}`

### 2. Invalid Email Rejection

```bash
curl -X POST "http://127.0.0.1:8000/students/register" \
  -H "Content-Type: application/json" \
  -d '{"name": "Bad Email", "email": "not-an-email", "password": "pass123"}'
```
→ **422** Pydantic validation error

### 3. Duplicate Email Rejection

```bash
curl -X POST "http://127.0.0.1:8000/students/register" \
  -H "Content-Type: application/json" \
  -d '{"name": "Another", "email": "student@lms.com", "password": "pass123"}'
```
→ **409** `"A student with this email already exists"`

### 4. Successful Login

```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "student@lms.com", "password": "stud123"}'
```
→ **200** `{token, user_id, role}`

### 5. Invalid Login Rejection

```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "student@lms.com", "password": "wrongpass"}'
```
→ **401** `"Invalid email or password"`

### 6. Rate-Limit Rejection

```bash
# Send 6 requests quickly
for ($i=0; $i -le 5; $i++) {
  curl -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"x@y.com","password":"z"}'
}
# 6th request →
```
→ **429** `"Rate limit exceeded"`

### 7. Student Attempting Admin Action

First login as student, capture `$TOKEN`:

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"student@lms.com","password":"stud123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X DELETE "http://127.0.0.1:8000/courses/course-1" -H "X-Auth-Token: $TOKEN"
```
→ **403** `"Only admins can perform this action"`

### 8. Instructor Creating a Course

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"instructor@lms.com","password":"instr123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X POST "http://127.0.0.1:8000/courses" \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: $TOKEN" \
  -d '{"title": "Python 101", "description": "Introduction to Python programming", "max_seats": 30}'
```
→ **201** `{id, title, description, max_seats, instructor_id, created_at}`

### 9. Student Enrolling in a Course

```bash
STUDENT_TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"student@lms.com","password":"stud123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# First, get course ID from instructor creation above, or list courses
COURSE_ID="course-<uuid-from-step-8>"

curl -X POST "http://127.0.0.1:8000/courses/$COURSE_ID/enroll" -H "X-Auth-Token: $STUDENT_TOKEN"
```
→ **200** `"Enrolled successfully"`

### 10. Duplicate Enrollment Rejection

```bash
curl -X POST "http://127.0.0.1:8000/courses/$COURSE_ID/enroll" -H "X-Auth-Token: $STUDENT_TOKEN"
```
→ **409** `"Already enrolled in this course"`

### 11. Course Seat Limit Rejection

Create a course with `max_seats: 1`, have one student enroll, then have a second student try:

```bash
# Instructor creates course with 1 seat
INSTR_TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"instructor@lms.com","password":"instr123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

FULL_COURSE=$(curl -s -X POST "http://127.0.0.1:8000/courses" -H "Content-Type: application/json" -H "X-Auth-Token: $INSTR_TOKEN" -d '{"title":"Full Course","description":"Only one seat available","max_seats":1}')
FULL_COURSE_ID=$(echo $FULL_COURSE | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Student 1 (pre-seeded) enrolls — succeeds
STUDENT_TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"student@lms.com","password":"stud123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X POST "http://127.0.0.1:8000/courses/$FULL_COURSE_ID/enroll" -H "X-Auth-Token: $STUDENT_TOKEN"

# Register a new student
curl -s -X POST "http://127.0.0.1:8000/students/register" -H "Content-Type: application/json" -d '{"name":"Student 2","email":"student2@test.com","password":"pass123"}'

STUDENT2_TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"student2@test.com","password":"pass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X POST "http://127.0.0.1:8000/courses/$FULL_COURSE_ID/enroll" -H "X-Auth-Token: $STUDENT2_TOKEN"
```
→ **400** `"Course is full (maximum seats reached)"`

### 12. Safe Error Handling

```bash
curl -X GET "http://127.0.0.1:8000/courses/nonexistent"
```
→ **404** `{"detail": "Course not found"}` — no stack trace, no internal details

### 13. Invalid API-Key (Token) Rejection

```bash
curl -X POST "http://127.0.0.1:8000/courses" \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: invalid-token" \
  -d '{"title":"Hacked","description":"Should not work","max_seats":10}'
```
→ **401** `"Invalid or expired token"`

### 14. CORS Configuration

CORS is configured to allow only:
```python
allow_origins=["http://localhost:3000", "http://localhost:5137"]
```

Any other origin (e.g. `http://localhost:9999`) making a browser request will be **blocked by the browser** with a CORS error in the console. Requests from curl/Postman bypass CORS (CORS is browser-only).

### 15. Secret Loading from .env

All secrets are loaded from `.env`:
```
ADMIN_EMAIL=admin@lms.com
ADMIN_PASSWORD=admin123
INSTRUCTOR_EMAIL=instructor@lms.com
INSTRUCTOR_PASSWORD=instr123
STUDENT_EMAIL=student@lms.com
STUDENT_PASSWORD=stud123
```

The `.env` file is in `.gitignore` — only `example.env` with placeholder values is committed.

## Code Flow Diagrams

### POST /auth/login — Successful Authentication

```
Client                              Server
  │                                    │
  │  POST /auth/login                  │
  │  Body: {email, password}          │
  │ ──────────────────────────────►   │
  │                                    ├─ slowapi rate limit (5/min) ✓
  │                                    ├─ Pydantic validate body ✓
  │                                    ├─ Loop users, find email match
  │                                    │  └─ Found! Compare password ✓
  │                                    ├─ secrets.token_urlsafe(32)
  │                                    ├─ tokens[token] = user_id
  │  ◄────────────────────────────── │
  │  200 {token, user_id, role}       │
```

### POST /courses — Instructor Creates Course

```
Instructor                          Server
  │                                    │
  │  POST /courses                     │
  │  X-Auth-Token: <token>            │
  │  Body: {title, description,       │
  │         max_seats: 30}            │
  │ ──────────────────────────────►   │
  │                                    ├─ get_current_user → user dict
  │                                    ├─ require_course_creator
  │                                    │  └─ role in (instructor, admin)? ✓
  │                                    │
  │                                    ├─ Pydantic validate body ✓
  │                                    ├─ Check unique title ✓
  │                                    │
  │                                    ├─ uuid4() → course_id
  │                                    ├─ Store in courses dict
  │                                    ├─ enrollments[course_id] = []
  │                                    ├─ log_action("course_created", ...)
  │                                    │
  │  ◄────────────────────────────── │
  │  201 {id, title, description,     │
  │       max_seats, instructor_id,   │
  │       created_at}                 │
```

### POST /courses/{course_id}/enroll — Validate-Then-Mutate

```
Student                             Server
  │                                    │
  │  POST /courses/{id}/enroll        │
  │  X-Auth-Token: <token>            │
  │ ──────────────────────────────►   │
  │                                    ├─ require_student → role check ✓
  │                                    │
  │                                    ├─ [VALIDATE] Course exists? ✓
  │                                    ├─ [VALIDATE] Not already enrolled? ✓
  │                                    ├─ [VALIDATE] Seats available? ✓
  │                                    │
  │                                    ├─ [MUTATE] enrollments[id].push(student)
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {message: "Enrolled           │
  │        successfully", ...}         │
```

### POST /students/register — All Failure Cases

```
Scenario 1: Invalid email → 422
Scenario 2: Duplicate email → 409
Scenario 3: Too short name → 422
Scenario 4: Too short password → 422
```

### DELETE /courses/{course_id} — Admin Only + Cascade

```
Admin                               Server
  │                                    │
  │  DELETE /courses/{id}             │
  │  X-Auth-Token: <token>            │
  │ ──────────────────────────────►   │
  │                                    ├─ require_admin → role = admin ✓
  │                                    ├─ Course exists? ✓
  │                                    │
  │                                    ├─ log_action("course_deleted", ...)
  │                                    ├─ lessons.pop(id)       ← cascade
  │                                    ├─ enrollments.pop(id)   ← cascade
  │                                    ├─ courses.pop(id)       ← delete
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {message: "Course deleted     │
  │        successfully"}             │
```

### GET /students/{student_id}/courses — Self Only

```
Student                             Server
  │                                    │
  │  GET /students/{id}/courses       │
  │  X-Auth-Token: <token>            │
  │ ──────────────────────────────►   │
  │                                    ├─ get_current_user → user
  │                                    ├─ user["id"] == student_id? ✓
  │                                    ├─ Lookup enrolled courses
  │  ◄────────────────────────────── │
  │  200 {count: N, courses: [...]}   │
```

## Pydantic Models

### StudentRegister

```python
class StudentRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
```

### LoginRequest

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

### CourseCreate

```python
class CourseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=1000)
    max_seats: int = Field(ge=1, le=1000)
```

### LessonCreate

```python
class LessonCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=10)
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Successful login, enroll, list, view, delete |
| 201 | Created | Student registered, course created, lesson created |
| 400 | Bad Request | Course full, invalid input |
| 401 | Unauthorized | Invalid/missing/expired token, bad login |
| 403 | Forbidden | Wrong role for action (student on admin route) |
| 404 | Not Found | Course or resource doesn't exist |
| 409 | Conflict | Duplicate email, duplicate enrollment, duplicate course title |
| 422 | Validation Error | Pydantic field validation failure |
| 429 | Too Many Requests | Login rate limit exceeded |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic[email] slowapi
```

### 2. Set environment variables

A `.env` file is provided with default accounts:

```
ADMIN_EMAIL=admin@lms.com
ADMIN_PASSWORD=admin123
INSTRUCTOR_EMAIL=instructor@lms.com
INSTRUCTOR_PASSWORD=instr123
STUDENT_EMAIL=student@lms.com
STUDENT_PASSWORD=stud123
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs.

- `POST /auth/login` → no auth needed, get a token
- Click **Authorize** and paste the token into the `X-Auth-Token` field
- All protected endpoints are now accessible

### 5. Test via curl

See the 15 testing scenarios above for complete curl commands.

## Security Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Token-based auth | `secrets.token_urlsafe(32)` | Cryptographically secure session tokens |
| Role-based authorization | `require_student`, `require_course_creator`, `require_lesson_creator`, `require_admin` | Each guard checks role and returns 403 on mismatch |
| Rate limiting | slowapi `5/minute` on login | Prevents brute-force password guessing |
| CORS | Exact origins whitelist | No wildcard — prevents unauthorized browser origins |
| Pydantic validation | `EmailStr`, `Field(min_length)`, `Field(ge)` | Invalid data rejected at boundary before processing |
| Environment variables | `load_dotenv()` + `os.getenv()` | No secrets in source code |
| Safe exception handling | No stack traces in responses | Custom HTTPException messages only |
| Audit logging | `log_action()` on course create/delete | Immutable append-only trail |
| Duplicate prevention | Checks for unique email, title, enrollment | 409 Conflict for all duplicates |
| Course deletion cascade | Removes lessons + enrollments + course | No orphaned data |
