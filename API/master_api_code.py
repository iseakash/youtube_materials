"""
master_api_code.py — Combined reference of all FastAPI patterns used across tasks.

Launch: uvicorn master_api_code:app --reload
Test:    http://127.0.0.1:8000/docs

Sections:
  1. Basics      — Simple GET, Path/Query params, basic Pydantic model
  2. CRUD        — Full Create/Read/Update/Delete + EmailStr/Field validation
  3. Security    — APIKeyHeader + Security/Depends, slowapi rate limiting, CORS, multi-role
"""

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Path, Query, status
from typing import Annotated
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import BaseModel, EmailStr, Field, Header
from dotenv import load_dotenv
import os

app = FastAPI(title="Master API Code — FastAPI Security Patterns")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 1: Basics — Simple GET, Path/Query Params, Basic Pydantic          ║
# ║                                                                              ║
# ║  Demonstrates: path parameters, query parameters with Annotated[Query],     ║
# ║  basic Pydantic model, and simple GET/POST endpoints.                       ║
# ║                                                                              ║
# ║  Test: GET /courses → ["gen ai", "python", "ML"]                           ║
# ║        GET /student/5 → {"student_id": 5}                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@app.get("/")
def test():
    return "I am Akash Gupta. My name"


@app.get("/courses")
def get_courses():
    return ["gen ai", "python", "ML"]


@app.get("/student/{student_id}")
def get_student(student_id: int):
    return {"student_id": student_id}


@app.get("/course/{course_id}/lesson/{lesson_id}")
def get_lesson(course_id: int, lesson_id: int):
    return {"course_id": course_id, "lesson_id": lesson_id}


@app.get("/stude")
def get_stud(course: str | None = None, limit: int = 10):
    return {"courses": course, "limit": limit}


@app.get("/search")
def search(keyword: Annotated[str, Query(min_length=2, max_length=50)], limit: Annotated[int, Query(ge=1, le=100)] = 10):
    return {"keyword": keyword, "limit": limit}


class StudentBasic(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    age: int = Field(ge=16, le=100)
    courses: str = Field(min_length=2, max_length=500)


@app.post("/createstud")
def create_student_basic(stud: StudentBasic):
    return {"msg": "student created", "student": stud}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 2: CRUD — Full Create/Read/Update/Delete + Validation              ║
# ║                                                                              ║
# ║  Demonstrates: in-memory list store, full CRUD, EmailStr, Field constraints,║
# ║  duplicate detection (409), partial updates (PATCH), custom Header() auth,  ║
# ║  status.HTTP_ codes, and query filtering.                                   ║
# ║                                                                              ║
# ║  Test: GET /students?course=fastapi                                        ║
# ║        POST /add_student with body                                         ║
# ║        GET /auth with X-API-Key: euron123 header                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    age: int = Field(ge=16, le=90)
    course: str = Field(min_length=2, max_length=90)


class StudentUpdate(BaseModel):
    name: str = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    age: int = Field(default=None, ge=16, le=90)
    course: str = Field(default=None, min_length=2, max_length=90)


students = [
    {"id": 1, "name": "sudh", "email": "sudh@gmail.com", "age": 35, "course": "fastapi"},
    {"id": 2, "name": "rahul", "email": "rahul@gmail.com", "age": 34, "course": "python"},
]


@app.get("/students")
def get_student_list(course: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 10):
    result = students
    if course:
        result = [s for s in students if s["course"].lower() == course.lower()]
    return {"count": len(result[:limit]), "Students": result[:limit]}


@app.post("/add_student")
def create_student(student: StudentCreate):
    for existing in students:
        if existing["email"] == student.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A Student with this mail id already there in DB",
            )

    new_student = {
        "id": max([item["id"] for item in students], default=0) + 1,
        **student.model_dump(),
    }
    students.append(new_student)
    return new_student


@app.put("/students/{student_id}")
def replace_student(student_id: int, student: StudentCreate):
    for index, existing in enumerate(students):
        if existing["id"] == student_id:
            replacement = {"id": student_id, **student.model_dump()}
            students[index] = replacement
            return replacement
    raise HTTPException(status_code=404, detail="Student id not found ")


@app.patch("/student_patch/{student_id}")
def update_student(student_id: int, student: StudentUpdate):
    for index, existing in enumerate(students):
        if existing["id"] == student_id:
            update_data = student.model_dump(exclude_unset=True)
            updated = {**existing, **update_data}
            students[index] = updated
            return updated
    raise HTTPException(status_code=404, detail="Student id not found ")


@app.delete("/student_del/{student_id}")
def delete_student(student_id: int):
    for index, student in enumerate(students):
        if student["id"] == student_id:
            students.pop(index)
            return students
    raise HTTPException(status_code=404, detail="Student id not found ")


@app.get("/browser")
def browser(user_agent: Annotated[str | None, Header()] = None):
    return {"browser": user_agent}


@app.get("/auth")
def auth_endpoint(x_api_key: Annotated[str | None, Header()] = None):
    if x_api_key != "euron123":
        raise HTTPException(status_code=401, detail=" your key is not valid ")
    return {"message": "you are authorized"}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 3: Security — APIKey Auth, Rate Limiting, CORS, Multi-Role         ║
# ║                                                                              ║
# ║  Demonstrates: APIKeyHeader + Security/Depends, .env secret loading,        ║
# ║  slowapi rate limiting, CORSMiddleware, multi-role auth (user vs admin).    ║
# ║                                                                              ║
# ║  NOTE: GET /courses exists in Section 1 (no auth). This section's version   ║
# ║  is renamed to GET /courses_secure to avoid a route conflict.                ║
# ║                                                                              ║
# ║  Test: POST /login with body {"username":"admin","password":"akash123"}     ║
# ║        GET /news (rate-limited to 5/min)                                    ║
# ║        GET /courses_secure with X-API-Key header                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

load_dotenv()

API_KEY = os.getenv("API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing api key")
    return key


@app.get("/health")
def health_check():
    return {"status": "running", "message": "The API is running"}


# Renamed from /courses to avoid route collision with Section 1's GET /courses
@app.get("/courses_secure")
def get_courses_secure(key: str = Security(verify_api_key)):
    return {"course": ["pythhon", "ml", "gen ai"]}


def verify_api_key_depends(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Auth Failed")
    return key


@app.get("/coursesdepends", dependencies=[Depends(verify_api_key_depends)])
def get_courses_depends():
    return {"course": ["r", "ml", "gen ai"]}


USER_KEY = os.getenv("USER_KEY")
ADMIN_KEY = os.getenv("ADMIN_KEY")

user_key_header = APIKeyHeader(name="X-User-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_user_key(key: str = Depends(user_key_header)):
    if key != USER_KEY:
        raise HTTPException(status_code=401, detail="Auth Failed for User")
    return key


def require_admin_key(key: str = Depends(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Auth Failed for Admin")
    return key


@app.get("/getcoursesuser", dependencies=[Depends(require_user_key)])
def list_courses_user():
    return {"course": ["python", "ml", "dl"]}


@app.delete("/deletecourse/{course_name}", dependencies=[Depends(require_admin_key)])
def delete_course(course_name: str):
    return {"msg": f"successfully you are able to delete: {course_name}"}


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/news")
@limiter.limit("5/minute")
def get_news(request: Request):
    return {"news": ["Akash is a data scientist", "today is monday"]}


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
@limiter.limit("2/minute")
def login(request: Request, credential: LoginRequest):
    if credential.username != "admin" and credential.password != "akash123":
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"msg": "You are Welcome!"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5137"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "X-Api-Key"],
)


@app.get("/dashboard")
def get_dashboard():
    return {"msg": "Yes, you have the access", "data": "all the course"}
