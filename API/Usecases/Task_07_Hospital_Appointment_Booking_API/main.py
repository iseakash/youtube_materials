from fastapi import FastAPI, HTTPException, Security, Request
import os
import uuid
from datetime import datetime, date
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

app = FastAPI(title="Hospital Appointment Booking API")

API_KEY = os.getenv("API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


DOCTORS = {
    15: {"name": "Dr. Sharma",    "specialty": "Cardiologist"},
    21: {"name": "Dr. Patel",     "specialty": "Dermatologist"},
    32: {"name": "Dr. Verma",     "specialty": "Neurologist"},
}

appointments = {}


class AppointmentCreate(BaseModel):
    patient_name: str = Field(min_length=2, max_length=100)
    patient_email: EmailStr
    doctor_id: int
    appointment_date: str = Field(min_length=10, max_length=10)
    time_slot: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def parse_date(date_str: str) -> date:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )


def time_slot_to_minutes(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.post("/appointments", status_code=201)
@limiter.limit("10/minute")
def create_appointment(request: Request, appointment_data: AppointmentCreate):
    appointment_date = parse_date(appointment_data.appointment_date)

    if appointment_date <= date.today():
        raise HTTPException(
            status_code=400,
            detail="Appointment date cannot be in the past"
        )

    doctor = DOCTORS.get(appointment_data.doctor_id)
    if doctor is None:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found"
        )

    new_slot_minutes = time_slot_to_minutes(appointment_data.time_slot)

    for existing in appointments.values():
        if (existing["doctor_id"] == appointment_data.doctor_id and
                existing["appointment_date"] == appointment_data.appointment_date):
            existing_minutes = time_slot_to_minutes(existing["time_slot"])
            if abs(new_slot_minutes - existing_minutes) < 15:
                raise HTTPException(
                    status_code=409,
                    detail="Time slot conflicts with an existing appointment. Slots must be at least 15 minutes apart."
                )

    appointment_id = str(uuid.uuid4())

    appointments[appointment_id] = {
        "appointment_id": appointment_id,
        "patient_name": appointment_data.patient_name,
        "patient_email": appointment_data.patient_email,
        "doctor_id": appointment_data.doctor_id,
        "doctor_name": doctor["name"],
        "specialty": doctor["specialty"],
        "appointment_date": appointment_data.appointment_date,
        "time_slot": appointment_data.time_slot,
    }

    return {
        "message": "Appointment booked successfully",
        "appointment_id": appointment_id,
    }


@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: str):
    appointment = appointments.get(appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )
    return appointment


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str, key: str = Security(verify_api_key)):
    appointment = appointments.get(appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    del appointments[appointment_id]

    return {"message": "Appointment cancelled successfully"}
