"""
Secure Book Library API — allows users to borrow/return books with a max-3 limit and rate-limited borrowing.

Key imports explained:
- APIKeyHeader: extracts X-User-Key header for Security() registration in Swagger
- Security(): registers the user key scheme in OpenAPI so Swagger UI shows an Authorize button
- slowapi: rate-limits the borrow endpoint to 5 requests per minute per IP
- Limiter + get_remote_address: creates an IP-based rate limiter
- _rate_limit_exceeded_handler: returns a proper 429 JSON response instead of a raw exception
- Request: required as first parameter when using slowapi with a Pydantic body
"""

from fastapi import FastAPI, HTTPException, Security, Depends, Request
import os
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Secure Book Library API")

USER_KEYS = {
    "user-alice": os.getenv("ALICE_KEY"),
    "user-bob": os.getenv("BOB_KEY"),
}

user_key_header = APIKeyHeader(name="X-User-Key", auto_error=False)


def identify_user(key: str = Security(user_key_header)):
    for user_id, expected_key in USER_KEYS.items():
        if key == expected_key:
            return user_id
    raise HTTPException(
        status_code=401,
        detail="Invalid user key"
    )


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


books = {
    "book-1": {"id": "book-1", "title": "Python 101", "author": "John Doe", "available": True},
    "book-2": {"id": "book-2", "title": "FastAPI Guide", "author": "Jane Smith", "available": True},
    "book-3": {"id": "book-3", "title": "Machine Learning", "author": "Sam Wilson", "available": True},
    "book-4": {"id": "book-4", "title": "Data Structures", "author": "Lisa Ray", "available": True},
    "book-5": {"id": "book-5", "title": "Algorithms", "author": "Tom Hardy", "available": True},
}

borrowed_books: dict[str, list[str]] = {}


class BookOut(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=100)
    available: bool


@app.get("/books")
def list_books():
    return [BookOut(**book) for book in books.values()] # The ** operator unpacks that dictionary so Pydantic can read the keys as field names


@app.post("/books/{book_id}/borrow")
@limiter.limit("5/minute")
def borrow_book(request: Request, book_id: str, user_id: str = Security(identify_user)):
    book = books.get(book_id)
    if not book:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    if not book["available"]:
        raise HTTPException(
            status_code=400,
            detail="Book is not available"
        )

    user_books = borrowed_books.get(user_id, [])
    if len(user_books) >= 3:
        raise HTTPException(
            status_code=400,
            detail="Borrow limit reached (max 3 books)"
        )

    book["available"] = False
    borrowed_books.setdefault(user_id, []).append(book_id)

    return BookOut(**book)


@app.post("/books/{book_id}/return")
def return_book(book_id: str, user_id: str = Security(identify_user)):
    book = books.get(book_id)
    if not book:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    if book["available"]:
        raise HTTPException(
            status_code=400,
            detail="Book was not borrowed"
        )

    user_books = borrowed_books.get(user_id, [])
    if book_id not in user_books:
        raise HTTPException(
            status_code=403,
            detail="You did not borrow this book"
        )

    user_books.remove(book_id)
    book["available"] = True

    return BookOut(**book)


@app.get("/users/{user_id}/borrowed-books")
def get_borrowed_books(user_id: str, auth_user_id: str = Security(identify_user)):
    if user_id != auth_user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own borrowed books"
        )

    user_book_ids = borrowed_books.get(user_id, [])
    user_books = [BookOut(**books[bid]) for bid in user_book_ids if bid in books]

    return {"count": len(user_books), "books": user_books}
