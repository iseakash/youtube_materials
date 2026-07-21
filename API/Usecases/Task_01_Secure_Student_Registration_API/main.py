import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from models import StudentCreate

load_dotenv()

app = FastAPI(title="Student Registration API", version="1.0.0")

STUDENT_API_KEY = os.getenv("STUDENT_API_KEY")
if not STUDENT_API_KEY:
    raise RuntimeError("STUDENT_API_KEY not set in .env file")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# In-memory list to store registered students
students: list[dict] = []


def verify_api_key(key: str = Security(api_key_header)):
    if key != STUDENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return key


@app.post("/add_student", status_code=status.HTTP_201_CREATED)
def create_student(student: StudentCreate, api_key: str = Security(verify_api_key)):
    # Check for duplicate email
    for existing in students:
        if existing["email"] == student.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this email already exists in DB",
            )

    # Auto-generate student ID
    new_student = {
        "id": max([item["id"] for item in students], default=0) + 1,
        **student.model_dump(),
    }

    students.append(new_student)
    return new_student


@app.get("/students")
def get_student():
    return {"count": len(students), "Students": students}
