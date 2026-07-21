# Secure Student Registration API

A FastAPI-based REST API for student registration with API key authentication.

## Features

- POST `/add_student` — Register a new student
- Input validation (name, email, age, course)
- Duplicate email detection
- API key authentication via `X-API-Key` header
- In-memory data storage (list)

## Requirements

- Python 3.10+
- pip

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the API key**
   
   Edit the `.env` file and set your secret key:
   ```
   STUDENT_API_KEY=your-secret-key-here
   ```

3. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```

   The API will be available at `http://localhost:8000`.

## API Usage

### Register a Student

**Endpoint:** `POST /add_student`

**Headers:**
```
X-API-Key: your-secret-key-here
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Rahul Kumar",
  "email": "rahul@example.com",
  "age": 24,
  "course": "FastAPI"
}
```

**Success Response (201):**
```json
{
  "id": 1,
  "name": "Rahul Kumar",
  "email": "rahul@example.com",
  "age": 24,
  "course": "FastAPI"
}
```

**Error Responses:**
- `401` — Invalid or missing API key
- `409` — A student with this email already exists in DB
- `422` — Validation error (invalid input)

## Testing with Swagger UI

Navigate to `http://localhost:8000/docs` in your browser. Click "Authorize" and enter your API key, then test the endpoint.
