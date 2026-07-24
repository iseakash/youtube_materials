"""
Complete Secure Learning Management System API — role-based LMS with auth, rate limiting, and audit logging.

Key imports explained:
- APIKeyHeader: extracts X-Auth-Token header for token-based auth registration in Swagger
- slowapi: rate-limits login to 5 attempts per minute per IP (prevents brute-force)
- CORSMiddleware: restricts browser access to whitelisted frontend origins
- EmailStr: validates email format at the Pydantic boundary (rejects malformed addresses)
- secrets.token_urlsafe: generates cryptographically secure session tokens (32 bytes → 43-char string)
- uuid.uuid4: generates unique IDs for courses, lessons, and student records
- datetime(timezone.utc): generates immutable UTC timestamps for audit trail integrity
"""

from fastapi import FastAPI, HTTPException, Security, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
import os
import secrets
import uuid
from datetime import datetime, timezone

load_dotenv()

app = FastAPI(title="Secure Learning Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5137"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Pre-seeded users ──────────────────────────────────────────────────────────

users = [
    {"id": "user-admin", "name": "Admin", "email": os.getenv("ADMIN_EMAIL"), "password": os.getenv("ADMIN_PASSWORD"), "role": "admin"},
    {"id": "user-instr", "name": "Instructor", "email": os.getenv("INSTRUCTOR_EMAIL"), "password": os.getenv("INSTRUCTOR_PASSWORD"), "role": "instructor"},
    {"id": "user-stud", "name": "Student", "email": os.getenv("STUDENT_EMAIL"), "password": os.getenv("STUDENT_PASSWORD"), "role": "student"},
]

# ─── Data stores ───────────────────────────────────────────────────────────────

tokens: dict[str, str] = {}
courses: dict[str, dict] = {}
enrollments: dict[str, list[str]] = {}
lessons: dict[str, list[dict]] = {}
audit_logs: list[dict] = []

# ─── Pydantic models ───────────────────────────────────────────────────────────

class StudentRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class CourseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=1000)
    max_seats: int = Field(ge=1, le=1000)

class LessonCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=10)

# ─── Auth helpers ──────────────────────────────────────────────────────────────

auth_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)


def get_current_user(token: str = Security(auth_header)):
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token"
    )


def require_student(user: dict = Depends(get_current_user)):
    if user["role"] != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can perform this action"
        )
    return user


def require_course_creator(user: dict = Depends(get_current_user)):
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instructors and admins can create courses"
        )
    return user


def require_lesson_creator(user: dict = Depends(get_current_user)):
    if user["role"] != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instructors can create lessons"
        )
    return user


def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action"
        )
    return user

# ─── Audit helper ──────────────────────────────────────────────────────────────

def log_action(action: str, admin_id: str, resource: str, result: str, details: dict | None = None):
    audit_logs.append({
        "action": action,
        "admin": admin_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resource": resource,
        "result": result,
        "details": details,
    })

# ─── Public endpoints ──────────────────────────────────────────────────────────

@app.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, creds: LoginRequest):
    for user in users:
        if user["email"] == creds.email and user["password"] == creds.password:
            token = secrets.token_urlsafe(32)
            tokens[token] = user["id"]
            return {"token": token, "user_id": user["id"], "role": user["role"]}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password"
    )


@app.post("/students/register", status_code=status.HTTP_201_CREATED)
def register_student(student: StudentRegister):
    for existing in users:
        if existing["email"] == student.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this email already exists"
            )

    new_student = {
        "id": "user-" + str(uuid.uuid4()),
        "name": student.name,
        "email": student.email,
        "password": student.password,
        "role": "student",
    }
    users.append(new_student)
    return {"id": new_student["id"], "name": new_student["name"], "email": new_student["email"], "role": new_student["role"]}


@app.get("/courses")
def list_courses():
    return [{"id": cid, "title": c["title"], "description": c["description"], "max_seats": c["max_seats"], "enrolled": len(enrollments.get(cid, []))} for cid, c in courses.items()]


@app.get("/courses/{course_id}")
def get_course(course_id: str):
    course = courses.get(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    return {**course, "enrolled": len(enrollments.get(course_id, [])), "lessons": lessons.get(course_id, [])}

# ─── Protected endpoints ───────────────────────────────────────────────────────

@app.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(body: CourseCreate, user: dict = Depends(require_course_creator)):
    for course in courses.values():
        if course["title"] == body.title:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A course with this title already exists"
            )

    course_id = "course-" + str(uuid.uuid4())
    courses[course_id] = {
        "id": course_id,
        "title": body.title,
        "description": body.description,
        "max_seats": body.max_seats,
        "instructor_id": user["id"],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    enrollments[course_id] = []

    log_action("course_created", user["id"], course_id, "success", {"title": body.title})

    return courses[course_id]


@app.post("/courses/{course_id}/enroll")
def enroll_course(course_id: str, user: dict = Depends(require_student)):
    course = courses.get(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    if user["id"] in enrollments.get(course_id, []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course"
        )

    if len(enrollments.get(course_id, [])) >= course["max_seats"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course is full (maximum seats reached)"
        )

    enrollments.setdefault(course_id, []).append(user["id"])

    return {"message": "Enrolled successfully", "course_id": course_id, "course_title": course["title"]}


@app.get("/students/{student_id}/courses")
def get_student_courses(student_id: str, user: dict = Depends(get_current_user)):
    if user["id"] != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own enrolled courses"
        )

    enrolled_courses = []
    for cid, enrolled_students in enrollments.items():
        if student_id in enrolled_students:
            course = courses.get(cid)
            if course:
                enrolled_courses.append(course)

    return {"count": len(enrolled_courses), "courses": enrolled_courses}


@app.post("/courses/{course_id}/lessons", status_code=status.HTTP_201_CREATED)
def create_lesson(course_id: str, body: LessonCreate, user: dict = Depends(require_lesson_creator)):
    course = courses.get(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    lesson_id = "lesson-" + str(uuid.uuid4())
    new_lesson = {
        "id": lesson_id,
        "title": body.title,
        "content": body.content,
        "course_id": course_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    lessons.setdefault(course_id, []).append(new_lesson)

    return new_lesson


@app.delete("/courses/{course_id}")
def delete_course(course_id: str, user: dict = Depends(require_admin)):
    course = courses.get(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    log_action("course_deleted", user["id"], course_id, "success", {"title": course["title"]})

    lessons.pop(course_id, None)
    enrollments.pop(course_id, None)
    courses.pop(course_id, None)

    return {"message": "Course deleted successfully", "course_id": course_id}


@app.get("/admin/audit-logs")
def get_audit_logs(user: dict = Depends(require_admin)):
    return {"count": len(audit_logs), "logs": audit_logs}
