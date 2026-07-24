# File Upload Metadata API

A secure FastAPI-based file upload system for a student assignment portal with API key authentication, file type validation, size enforcement, and duplicate submission prevention.

## Features

- Upload assignment files (PDF, DOCX, ZIP only)
- Maximum file size: 5 MB
- Pre-defined valid students (S001–S005) and assignments (A001–A003)
- One submission per student per assignment (duplicate rejection with 409)
- Unique submission ID via UUID
- Safe UUID-based filenames on disk (original filename never used)
- API key authentication on all endpoints
- Return 413 for oversized files, 415 for unsupported types

## Architecture

```
┌──────────────┐
│   Client     │
│ (Multipart   │
│  Form Data)  │
└──────┬───────┘
       │  POST /assignments/upload
       │  Headers: X-API-Key
       │  Body: file + student_id + assignment_id
       ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Application                       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │               Request Pipeline                     │    │
│  │                                                    │    │
│  │  1. Auth Guard (Depends → APIKeyHeader)           │    │
│  │     └─ Invalid/missing key → 401                  │    │
│  │                                                    │    │
│  │  2. Extract Form fields: student_id, assignment_id │    │
│  │                                                    │    │
│  │  3. Validate student_id in VALID_STUDENTS          │    │
│  │     └─ Unknown student → 404                       │    │
│  │                                                    │    │
│  │  4. Validate assignment_id in VALID_ASSIGNMENTS    │    │
│  │     └─ Unknown assignment → 404                    │    │
│  │                                                    │    │
│  │  5. Check duplicate submission                     │    │
│  │     (student_id, assignment_id) in secondary index │    │
│  │     └─ Already exists → 409                        │    │
│  │                                                    │    │
│  │  6. Validate file extension                        │    │
│  │     Allowed: .pdf, .docx, .zip                     │    │
│  │     └─ Not allowed → 415                           │    │
│  │                                                    │    │
│  │  7. Read file content, check size ≤ 5 MB           │    │
│  │     └─ Too large → 413                             │    │
│  │                                                    │    │
│  │  8. ✓ ALL VALIDATIONS PASSED                       │    │
│  │     Generate UUID submission_id                    │    │
│  │     Generate safe UUID filename                    │    │
│  │     Write file to uploads/ directory               │    │
│  │     Store metadata in submissions dict             │    │
│  │     Index in submissions_by_student                │    │
│  │                                                    │    │
│  │  9. Return 201 + submission metadata               │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              In-Memory Data Stores                │    │
│  │                                                    │    │
│  │  VALID_STUDENTS     = {"S001", "S002", ...}       │    │
│  │  VALID_ASSIGNMENTS  = {"A001", "A002", ...}       │    │
│  │                                                    │    │
│  │  submissions = {                                   │    │
│  │    "uuid": {submission_id, student_id,             │    │
│  │             assignment_id, file_name,              │    │
│  │             original_filename, file_size,          │    │
│  │             content_type}                          │    │
│  │  }                                                  │    │
│  │                                                    │    │
│  │  submissions_by_student = {                        │    │
│  │    ("S001", "A001"): "uuid"  ← O(1) duplicate chk │    │
│  │  }                                                  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              File Storage (uploads/)              │    │
│  │                                                    │    │
│  │  uploads/a1b2c3d4-....pdf  ← safe UUID filename   │    │
│  │  uploads/e5f6g7h8-....docx ← original name NEVER  │    │
│  │  uploads/i9j0k1l2-....zip  ← used for storage     │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/assignments/upload` | X-API-Key | Upload an assignment file |
| GET | `/assignments/{submission_id}` | X-API-Key | Get submission metadata |
| GET | `/health` | None | Health check |

## Code Flow Diagrams

### POST /assignments/upload

```
Client                                   Server
  │                                        │
  │  POST /assignments/upload              │
  │  Headers: X-API-Key                    │
  │  Body: file + student_id + assign_id   │
  │ ──────────────────────────────────►    │
  │                                        ├─ require_api_key()
  │                                        │  └─ mismatch → 401
  │                                        ├─ student_id in VALID_STUDENTS?
  │                                        │  └─ No → 404
  │                                        ├─ assignment_id in VALID_ASSIGNMENTS?
  │                                        │  └─ No → 404
  │                                        ├─ (student, assign) dup check
  │                                        │  └─ Exists → 409
  │                                        ├─ ext in {.pdf, .docx, .zip}?
  │                                        │  └─ No → 415
  │                                        ├─ size ≤ 5 MB?
  │                                        │  └─ No → 413
  │                                        ├─ ✓ ALL PASS
  │                                        ├─ Generate UUIDs
  │                                        ├─ Write file to uploads/
  │                                        ├─ Store metadata
  │  ◄──────────────────────────────────  │
  │  201 {submission_id, student_id,       │
  │       assignment_id, file_name,        │
  │       file_size, content_type}         │
```

### GET /assignments/{submission_id}

```
Client                                   Server
  │                                        │
  │  GET /assignments/{submission_id}      │
  │  Headers: X-API-Key                    │
  │ ──────────────────────────────────►    │
  │                                        ├─ require_api_key()
  │                                        │  └─ mismatch → 401
  │                                        ├─ Lookup submission_id
  │                                        │  └─ Missing → 404
  │  ◄──────────────────────────────────  │
  │  200 {submission metadata}            │
```

## Pre-defined Valid IDs

### Students

| ID | Name |
|----|------|
| S001 | Student One |
| S002 | Student Two |
| S003 | Student Three |
| S004 | Student Four |
| S005 | Student Five |

### Assignments

| ID | Name |
|----|------|
| A001 | Assignment 1 |
| A002 | Assignment 2 |
| A003 | Assignment 3 |

Any student or assignment ID not in these sets returns 404.

## Security — Filename Safety

```python
original_filename = "homework (1).pdf"
ext = Path(original_filename).suffix.lower()   # ".pdf"
safe_filename = f"{uuid.uuid4()}{ext}"          # "a1b2...pdf"
```

The original filename is stored in metadata for reference, but the file on disk uses a UUID. This prevents:
- **Path traversal attacks** — `../../etc/passwd` becomes a harmless UUID name
- **Collisions** — two students naming files `homework.pdf` won't overwrite each other
- **Information leakage** — original name never appears in the filesystem path

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 201 | Created | File uploaded successfully |
| 200 | OK | Submission metadata retrieved |
| 401 | Unauthorized | Invalid/missing API key |
| 404 | Not Found | Student, assignment, or submission not found |
| 409 | Conflict | Duplicate submission (already submitted) |
| 413 | Payload Too Large | File exceeds 5 MB |
| 415 | Unsupported Media Type | File type not PDF, DOCX, or ZIP |
| 422 | Validation Error | Missing form fields |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
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
# Upload a file
curl -X POST "http://127.0.0.1:8000/assignments/upload" \
  -H "X-API-Key: secure-api-key-2024" \
  -F "file=@homework.pdf" \
  -F "student_id=S001" \
  -F "assignment_id=A001"

# Get submission metadata
curl -X GET "http://127.0.0.1:8000/assignments/<submission_id>" \
  -H "X-API-Key: secure-api-key-2024"

# Try unsupported file type — returns 415
curl -X POST "http://127.0.0.1:8000/assignments/upload" \
  -H "X-API-Key: secure-api-key-2024" \
  -F "file=@image.png" \
  -F "student_id=S001" \
  -F "assignment_id=A002"

# Try duplicate submission — returns 409
curl -X POST "http://127.0.0.1:8000/assignments/upload" \
  -H "X-API-Key: secure-api-key-2024" \
  -F "file@homework.pdf" \
  -F "student_id=S001" \
  -F "assignment_id=A001"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Only PDF, DOCX, ZIP | `ALLOWED_EXTENSIONS = {".pdf", ".docx", ".zip"}` | Checked before reading file content |
| Max 5 MB | `len(contents) > 5 * 1024 * 1024` | Checked after read, before write |
| Student + assignment required | `Form(...)` from FastAPI | Pydantic-style validation via type hint |
| One submission per assignment | `submissions_by_student[(sid, aid)]` dict | O(1) duplicate lookup |
| Unique submission ID | `str(uuid.uuid4())` | Non-guessable, no collisions |
| Don't use original filename | `uuid.uuid4() + original extension` | Prevents path traversal + collisions |
| Auth on upload | `Depends(require_api_key)` | Prevents anonymous uploads |
| Auth on GET | `Depends(require_api_key)` | Prevents anonymous metadata access |
| Pre-defined valid IDs | `VALID_STUDENTS` + `VALID_ASSIGNMENTS` sets | Early rejection before further processing |

## Comparison to Task 8 (Food Delivery)

| Aspect | Task 8 | Task 10 |
|--------|--------|---------|
| Request body | JSON (Pydantic model) | Multipart form (file + fields) |
| Auth | User & Admin keys (2 roles) | Single API key |
| Data store | RESTAURANTS dict + orders | VALID_STUDENTS/VALID_ASSIGNMENTS sets + submissions |
| Unique constraint | Order ID is UUID | Student-Assignment tuple is unique |
| File handling | None | File upload with type/size validation |
| Storage | In-memory dict only | In-memory dict + filesystem (uploads/) |
