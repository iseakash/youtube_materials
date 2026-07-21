import json
import os
from datetime import date, datetime
from itertools import count

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="Employee Attendance API", version="1.0.0")

# Parse employees and managers from .env
raw_employees: dict[str, str] = json.loads(os.getenv("EMPLOYEES", "{}"))
raw_managers: dict[str, str] = json.loads(os.getenv("MANAGERS", "{}"))

employees: dict[str, dict] = {}
for idx, (emp_key, emp_name) in enumerate(raw_employees.items(), start=1):
    employees[emp_key] = {"employee_id": idx, "name": emp_name}

managers: dict[str, dict] = {}
for idx, (mgr_key, mgr_name) in enumerate(raw_managers.items(), start=1):
    managers[mgr_key] = {"manager_id": idx, "name": mgr_name}

# In-memory attendance storage
attendance_records: list[dict] = []
record_id_counter = count(start=1)


def get_employee(x_employee_key: str = Header(None)):
    emp = employees.get(x_employee_key)
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return emp


def get_manager(x_manager_key: str = Header(None)):
    mgr = managers.get(x_manager_key)
    if mgr is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return mgr


@app.post("/attendance/check-in", status_code=status.HTTP_201_CREATED)
def check_in(emp: dict = Depends(get_employee)):
    today = date.today()
    emp_id = emp["employee_id"]

    for record in attendance_records:
        if record["employee_id"] == emp_id and record["check_in"].date() == today:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Already checked in today",
            )

    now = datetime.now()
    new_record = {
        "record_id": next(record_id_counter),
        "employee_id": emp_id,
        "employee_name": emp["name"],
        "check_in": now,
    }
    attendance_records.append(new_record)

    return {
        "message": "Check-in successful",
        "record_id": new_record["record_id"],
        "employee_id": emp_id,
        "employee_name": emp["name"],
        "check_in": now.isoformat(),
    }


@app.get("/attendance/my")
def get_my_attendance(emp: dict = Depends(get_employee)):
    emp_id = emp["employee_id"]
    my_records = [
        {
            "record_id": r["record_id"],
            "employee_id": r["employee_id"],
            "employee_name": r["employee_name"],
            "check_in": r["check_in"].isoformat(),
        }
        for r in attendance_records
        if r["employee_id"] == emp_id
    ]
    return {"count": len(my_records), "attendance": my_records}


@app.get("/attendance/all")
def get_all_attendance(mgr: dict = Depends(get_manager)):
    all_records = [
        {
            "record_id": r["record_id"],
            "employee_id": r["employee_id"],
            "employee_name": r["employee_name"],
            "check_in": r["check_in"].isoformat(),
        }
        for r in attendance_records
    ]
    return {"count": len(all_records), "attendance": all_records}
