# Secure Book Library API

A secure FastAPI-based digital library where users can browse, borrow, and return books. Enforces a maximum of 3 borrowed books per user, prevents double-borrowing, and rate-limits borrowing attempts.

## Features

- **Browse books** — no auth required to view the catalog
- **Borrow with rate limit** — max 5 borrow attempts per minute per IP
- **Max 3 books per user** — enforced server-side
- **Ownership enforcement** — only the borrower can return their book
- **Availability tracking** — a borrowed book cannot be borrowed by another user
- **Validate-then-mutate** — all checks complete before state changes
- **Swagger UI Authorize** — user key has a dedicated field

## Architecture

```
┌─────────────────────┐      ┌─────────────────────┐
│  Alice              │      │  Bob                │
│  Key: alice-key-... │      │  Key: bob-key-...   │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           │  X-User-Key + actions      │  X-User-Key + actions
           ▼                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  identify_user( Security )                            │    │
│  │  ── X-User-Key via APIKeyHeader                       │    │
│  │                                                       │    │
│  │  Maps key → user_id from USER_KEYS dict               │    │
│  │  Invalid key → 401                                    │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Rate Limiter (slowapi)                              │    │
│  │                                                       │    │
│  │  POST /books/{id}/borrow → 5/minute per IP           │    │
│  │  Exceeded → 429                                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Validate-Then-Mutate (borrow)                        │    │
│  │                                                       │    │
│  │  Step 1 (all validations, no mutations):              │    │
│  │    ├─ Book exists?          → 404                     │    │
│  │    ├─ Book available?       → 400                     │    │
│  │    └─ User has < 3 books?  → 400                     │    │
│  │                                                       │    │
│  │  Step 2 (only then mutate):                           │    │
│  │    ├─ book["available"] = False                       │    │
│  │    └─ borrowed_books[id].append(book_id)              │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Data Stores                                          │    │
│  │                                                       │    │
│  │  books = {                                            │    │
│  │    "book-1": {id, title, author, available},          │    │
│  │    ...                                                │    │
│  │  }                                                     │    │
│  │                                                       │    │
│  │  borrowed_books = {                                   │    │
│  │    "user-alice": ["book-1", "book-2"],                │    │
│  │    "user-bob": ["book-3"]                             │    │
│  │  }                                                     │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|-------------|-------------|
| GET | `/books` | No | No | List all books with availability |
| POST | `/books/{book_id}/borrow` | X-User-Key | 5/min | Borrow a book (if available) |
| POST | `/books/{book_id}/return` | X-User-Key | No | Return a borrowed book |
| GET | `/users/{user_id}/borrowed-books` | X-User-Key | No | View your borrowed books |

## Auth Strategy

User keys are mapped to user IDs in the server:

```python
USER_KEYS = {
    "user-alice": os.getenv("ALICE_KEY"),
    "user-bob": os.getenv("BOB_KEY"),
}
```

| Header | User ID | Key (from .env) |
|--------|---------|-----------------|
| `X-User-Key: alice-key-2024` | `user-alice` | `ALICE_KEY` |
| `X-User-Key: bob-key-2024` | `user-bob` | `BOB_KEY` |

The `identify_user()` dependency returns the user ID, which is used in the handler to track borrowed books and enforce ownership.

## Pydantic Models

### BookOut (response)

```python
class BookOut(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=100)
    available: bool
```

Returned by GET /books, POST borrow, POST return, and GET borrowed-books.

## Security Challenge: Validate-Then-Mutate

The core security challenge is ensuring that **all validations complete before any state change**. This prevents partial/corrupt state if an exception occurs mid-mutation.

### Borrow Flow (Validate-Then-Mutate)

```python
@app.post("/books/{book_id}/borrow")
@limiter.limit("5/minute")
def borrow_book(request, book_id, user_id):
    # ── Step 1: ALL validations — no state changes ──
    book = books.get(book_id)
    if not book:                          # 1. Book exists?
        raise HTTPException(status_code=404)

    if not book["available"]:             # 2. Book is available?
        raise HTTPException(status_code=400)

    user_books = borrowed_books.get(user_id, [])
    if len(user_books) >= 3:              # 3. User under limit?
        raise HTTPException(status_code=400)

    # ── Step 2: ONLY THEN mutate state ──
    book["available"] = False
    borrowed_books.setdefault(user_id, []).append(book_id)

    return BookOut(**book)
```

### Why This Matters

If we mutated state during validation (e.g., marking a book unavailable before checking the user's limit), and the user was over the limit, the book would be left in an inconsistent state — marked unavailable but not actually borrowed by anyone.

The validate-then-mutate pattern guarantees that **either all mutations succeed, or none are applied**.

## Code Flow Diagrams

### GET /books — List All Books

```
Client                              Server
  │                                    │
  │  GET /books                        │
  │ ──────────────────────────────►   │
  │                                    ├─ No auth required
  │                                    ├─ Return all books
  │  ◄────────────────────────────── │
  │  200 [{id, title, author,          │
  │        available: true},           │
  │       {id, title, author,          │
  │        available: false}]          │
```

### POST /books/{book_id}/borrow — Success

```
Alice                               Server
  │                                    │
  │  POST /books/book-1/borrow        │
  │  X-User-Key: alice-key-2024      │
  │ ──────────────────────────────►   │
  │                                    ├─ Rate limit check (5/min) ✓
  │                                    ├─ identify_user → "user-alice"
  │                                    │
  │                                    ├─ [VALIDATE] book-1 exists? ✓
  │                                    ├─ [VALIDATE] book-1 available? ✓
  │                                    ├─ [VALIDATE] alice has < 3? ✓
  │                                    │
  │                                    ├─ [MUTATE] available = False
  │                                    ├─ [MUTATE] alice borrows book-1
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {id: "book-1",               │
  │       title: "Python 101",        │
  │       author: "John Doe",         │
  │       available: false}           │
```

### POST /books/{book_id}/borrow — All Failure Cases

```
Scenario 1: Book not found
  Client → 404 {"detail": "Book not found"}

Scenario 2: Book already borrowed
  Client → 400 {"detail": "Book is not available"}

Scenario 3: User already has 3 books
  Alice                        Server
    │                             │
    │  POST /books/book-4/borrow │
    │  (already has 3 books)     │
    │ ──────────────────────►    │
    │                             ├─ [VALIDATE] < 3 books?
    │                             │  └─ No (already has 3)
    │  ◄────────────────────── │
    │  400 {"detail": "Borrow     │
    │        limit reached        │
    │        (max 3 books)"}      │

Scenario 4: Rate limit exceeded
  Alice                        Server
    │                             │
    │  (6th request in 1 minute) │
    │ ──────────────────────►    │
    │                             ├─ slowapi → 429
    │  ◄────────────────────── │
    │  429 {"detail": "Rate       │
    │        limit exceeded"}     │
```

### POST /books/{book_id}/return — Success

```
Alice                               Server
  │                                    │
  │  POST /books/book-1/return        │
  │  X-User-Key: alice-key-2024      │
  │ ──────────────────────────────►   │
  │                                    ├─ identify_user → "user-alice"
  │                                    ├─ [VALIDATE] book-1 exists? ✓
  │                                    ├─ [VALIDATE] book-1 is borrowed? ✓
  │                                    ├─ [VALIDATE] alice borrowed it? ✓
  │                                    │
  │                                    ├─ [MUTATE] available = True
  │                                    ├─ [MUTATE] remove from alice's list
  │                                    │
  │  ◄────────────────────────────── │
  │  200 {id: "book-1",               │
  │       title: "Python 101",        │
  │       author: "John Doe",         │
  │       available: true}            │
```

### POST /books/{book_id}/return — Wrong User

```
Bob tries to return Alice's book   Server
  │                                    │
  │  POST /books/book-1/return        │
  │  X-User-Key: bob-key-2024        │
  │ ──────────────────────────────►   │
  │                                    ├─ identify_user → "user-bob"
  │                                    ├─ [VALIDATE] book-1 exists? ✓
  │                                    ├─ [VALIDATE] book-1 is borrowed? ✓
  │                                    ├─ [VALIDATE] bob borrowed it?
  │                                    │  └─ No — Alice borrowed it
  │  ◄────────────────────────────── │
  │  403 {"detail": "You did not      │
  │        borrow this book"}         │
```

### GET /users/{user_id}/borrowed-books — Self Only

```
Alice                               Server
  │                                    │
  │  GET /users/user-alice/            │
  │       borrowed-books               │
  │  X-User-Key: alice-key-2024      │
  │ ──────────────────────────────►   │
  │                                    ├─ identify_user → "user-alice"
  │                                    ├─ user-alice == user-alice? ✓
  │                                    ├─ Lookup borrowed book IDs
  │                                    ├─ Fetch book details
  │  ◄────────────────────────────── │
  │  200 {count: 1, books: [{id,      │
  │       title, author,               │
  │       available: false}]}          │
```

```
Bob tries to view Alice's books    Server
  │                                    │
  │  GET /users/user-alice/            │
  │       borrowed-books               │
  │  X-User-Key: bob-key-2024        │
  │ ──────────────────────────────►   │
  │                                    ├─ identify_user → "user-bob"
  │                                    ├─ user-alice == user-bob?
  │                                    │  └─ No
  │  ◄────────────────────────────── │
  │  403 {"detail": "You can only     │
  │        view your own borrowed     │
  │        books"}                    │
```

## Pre-loaded Books

```python
books = {
    "book-1": {"id": "book-1", "title": "Python 101", "author": "John Doe", "available": True},
    "book-2": {"id": "book-2", "title": "FastAPI Guide", "author": "Jane Smith", "available": True},
    "book-3": {"id": "book-3", "title": "Machine Learning", "author": "Sam Wilson", "available": True},
    "book-4": {"id": "book-4", "title": "Data Structures", "author": "Lisa Ray", "available": True},
    "book-5": {"id": "book-5", "title": "Algorithms", "author": "Tom Hardy", "available": True},
}
```

## HTTP Status Codes

| Code | Meaning | Used When |
|------|---------|-----------|
| 200 | OK | Books listed, borrowed, returned, or borrowed list viewed |
| 400 | Bad Request | Book unavailable, borrow limit reached, book not borrowed |
| 401 | Unauthorized | Invalid or missing user key |
| 403 | Forbidden | Wrong user tries to return a book or view another user's books |
| 404 | Not Found | Book ID doesn't exist |
| 429 | Too Many Requests | Borrow rate limit exceeded (5/min) |

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic slowapi
```

### 2. Set user keys

A `.env` file is provided with default keys:

```
ALICE_KEY=alice-key-2024
BOB_KEY=bob-key-2024
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

### 4. Test via Swagger UI

Open http://127.0.0.1:8000/docs. Click **Authorize** and enter a user key (e.g. `alice-key-2024`).

### 5. Test via curl

```bash
# List all books (no auth required)
curl -X GET "http://127.0.0.1:8000/books"

# Alice borrows book-1
curl -X POST "http://127.0.0.1:8000/books/book-1/borrow" \
  -H "X-User-Key: alice-key-2024"

# Alice borrows book-2
curl -X POST "http://127.0.0.1:8000/books/book-2/borrow" \
  -H "X-User-Key: alice-key-2024"

# View Alice's borrowed books
curl -X GET "http://127.0.0.1:8000/users/user-alice/borrowed-books" \
  -H "X-User-Key: alice-key-2024"

# Alice returns book-1
curl -X POST "http://127.0.0.1:8000/books/book-1/return" \
  -H "X-User-Key: alice-key-2024"

# Bob tries to return Alice's book-2 (should fail with 403)
curl -X POST "http://127.0.0.1:8000/books/book-2/return" \
  -H "X-User-Key: bob-key-2024"

# Bob tries to view Alice's books (should fail with 403)
curl -X GET "http://127.0.0.1:8000/users/user-alice/borrowed-books" \
  -H "X-User-Key: bob-key-2024"

# Invalid key (should fail with 401)
curl -X GET "http://127.0.0.1:8000/books/book-1/borrow" \
  -H "X-User-Key: wrong-key"

# Borrow non-existent book (should fail with 404)
curl -X POST "http://127.0.0.1:8000/books/book-99/borrow" \
  -H "X-User-Key: alice-key-2024"
```

## Design Decisions

| Requirement | Implementation | Reasoning |
|-------------|---------------|-----------|
| Auth required for borrow/return | `APIKeyHeader` + `Security()` + `identify_user()` | Consistent with reference pattern; returns user_id for ownership checks |
| Max 3 books per user | `len(user_books) >= 3` check | Enforced server-side — client cannot bypass |
| Rate limit borrowing | slowapi `5/minute` | Prevents brute-force/abuse of the borrow endpoint |
| Validate-then-mutate | All checks before state changes | Prevents partial/corrupt state on failure |
| Only correct user can return | `book_id in user_books` check | Ownership verified before mutation |
| Same book cannot be double-borrowed | `book["available"]` flag | Atomic check + mutation prevents race conditions |
| Self-only borrowed list | Path user_id must match auth user_id | Prevents cross-user data access |
| Pydantic response model | `BookOut` model | Consistent structure across all responses |
