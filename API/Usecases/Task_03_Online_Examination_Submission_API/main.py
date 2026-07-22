from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import BaseModel, Field

load_dotenv()

API_KEY = os.getenv("API_KEY")

app = FastAPI(title="Online Examination Submission API")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key

submissions: dict[int, dict] = {}

class AnswerItem(BaseModel):
    question_id: int
    answer: str = Field(..., max_length=500)

class ExamSubmission(BaseModel):
    student_id: int
    exam_id: int
    answers: list[AnswerItem] = Field(..., min_length=1, max_length=100)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

@app.post("/exam/submit")
@limiter.limit("3/minute")
def submit_exam(request: Request, submission: ExamSubmission):
    if submission.student_id in submissions:
        raise HTTPException(
            status_code=409,
            detail="Duplicate submission. This student has already submitted an exam."
        )

    stored = {
        "student_id": submission.student_id,
        "exam_id": submission.exam_id,
        "answers": [item.model_dump() for item in submission.answers]
    }
    submissions[submission.student_id] = stored

    return JSONResponse(content=stored, status_code=201)

@app.get("/exam/result/{student_id}")
def get_result(student_id: int, key: str = Security(verify_api_key)):
    if student_id not in submissions:
        raise HTTPException(
            status_code=404,
            detail="No result found for this student."
        )
    return submissions[student_id]
