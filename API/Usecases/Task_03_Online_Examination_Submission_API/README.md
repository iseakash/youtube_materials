# Online Examination Submission API

An API for submitting and retrieving online exam results with rate limiting and API key authentication.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env` and set your API key:
```
API_KEY=your_api_key_here
```

## Run

```bash
uvicorn main:app --reload
```

Swagger UI available at `http://localhost:8000/docs`

## Endpoints

### POST /exam/submit
Submit an exam. Rate limited to 3 requests per minute per IP.

**Body:**
```json
{
  "student_id": 101,
  "exam_id": 501,
  "answers": [
    {
      "question_id": 1,
      "answer": "FastAPI is a Python framework"
    }
  ]
}
```

**Rules:**
- One submission per student (returns 409 on duplicate)
- 1 to 100 answers per submission
- Each answer max 500 characters

### GET /exam/result/{student_id}
Retrieve a student's submission. Requires `X-API-Key` header.

Returns 404 if no result exists for the student.

## Rate Limits
- POST `/exam/submit`: **3 requests per minute** per IP address
