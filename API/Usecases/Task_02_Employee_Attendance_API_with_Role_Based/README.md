# Employee Attendance API with Role-Based Access

A FastAPI-based attendance system with employee and manager roles.

## Features

- `POST /attendance/check-in` — Mark attendance (once per day)
- `GET /attendance/my` — View own attendance
- `GET /attendance/all` — View all attendance (manager only)
- Role-based access via `X-Employee-Key` and `X-Manager-Key` headers
- Keys never stored in attendance records or exposed in responses

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure keys in `.env`**
   ```
   EMPLOYEES={"emp-key-123":"Rahul Kumar","emp-key-456":"Priya Singh"}
   MANAGERS={"mgr-key-789":"Alice Wilson"}
   ```

3. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```

## API Usage

### Check In
`POST /attendance/check-in` — Header: `X-Employee-Key: emp-key-123`

Response `201`:
```json
{
  "message": "Check-in successful",
  "record_id": 1,
  "employee_id": 1,
  "employee_name": "Rahul Kumar",
  "check_in": "2026-07-21T10:30:00"
}
```

### My Attendance
`GET /attendance/my` — Header: `X-Employee-Key: emp-key-123`

### All Attendance (Manager only)
`GET /attendance/all` — Header: `X-Manager-Key: mgr-key-789`

## Error Responses

- `403` — Access denied (invalid key)
- `409` — Already checked in today
