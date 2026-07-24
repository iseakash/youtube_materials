from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form  # web framework, error handling, DI, file upload, form field
import os                                           # read env vars, file path ops
from pathlib import Path                            # build absolute path to .env
import uuid                                         # generate unique submission IDs and safe filenames
from dotenv import load_dotenv                      # load .env file into os.environ
from fastapi.security import APIKeyHeader           # extract API key from HTTP header
from pydantic import BaseModel, Field               # schema validation, field constraints

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="File Upload Metadata API")

API_KEY = os.getenv("API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")


def require_api_key(key: str = Depends(api_key_header)):
    """Guard: rejects the request if X-API-Key header doesn't match the stored API_KEY."""
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".zip"}

VALID_STUDENTS = {"S001", "S002", "S003", "S004", "S005"}
VALID_ASSIGNMENTS = {"A001", "A002", "A003"}

submissions: dict[str, dict] = {}

submissions_by_student: dict[tuple[str, str], str] = {}  # tuple (student_id, assignment_id) is hashable → O(1) duplicate check


class SubmissionMetadata(BaseModel):
    submission_id: str
    student_id: str
    assignment_id: str
    file_name: str
    original_filename: str
    file_size: int
    content_type: str


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.post("/assignments/upload", status_code=201)
async def upload_assignment(
    file: UploadFile = File(...),          # ... (Ellipsis) means required — FastAPI rejects with 422 if missing
    student_id: str = Form(...),           # Form() tells FastAPI this comes from multipart form data, not JSON body
    assignment_id: str = Form(...),         # Same — required because file upload requires multipart/form-data
    key: str = Depends(require_api_key),
):
    """Validates student, assignment, file type, size, and duplicate — then saves with a safe UUID filename."""

    if student_id not in VALID_STUDENTS:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    if assignment_id not in VALID_ASSIGNMENTS:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found"
        )

    dup_key = (student_id, assignment_id)
    if dup_key in submissions_by_student:   # tuple is hashable → O(1) dict lookup
        raise HTTPException(
            status_code=409,
            detail="Already submitted for this assignment"
        )

    original_filename = file.filename or "unknown"
    ext = Path(original_filename).suffix.lower()  # extract extension like ".pdf" from full filename

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Only PDF, DOCX, and ZIP files are allowed"
        )

    contents = await file.read()               # await = async I/O — read file bytes without blocking the server thread

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 5 MB"
        )

    submission_id = str(uuid.uuid4())
    safe_filename = f"{uuid.uuid4()}{ext}"

    file_path = UPLOAD_DIR / safe_filename
    file_path.write_bytes(contents)          # Path.write_bytes() — writes raw bytes directly to disk, no open() needed

    metadata = {
        "submission_id": submission_id,
        "student_id": student_id,
        "assignment_id": assignment_id,
        "file_name": safe_filename,
        "original_filename": original_filename,
        "file_size": len(contents),
        "content_type": file.content_type or "application/octet-stream",
    }

    submissions[submission_id] = metadata
    submissions_by_student[dup_key] = submission_id

    return metadata


@app.get("/assignments/{submission_id}")
def get_submission(
    submission_id: str,
    key: str = Depends(require_api_key),
):
    """Returns submission metadata for the given submission_id."""
    metadata = submissions.get(submission_id)
    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found"
        )

    return metadata
