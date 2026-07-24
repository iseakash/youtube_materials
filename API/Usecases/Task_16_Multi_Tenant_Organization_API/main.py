from fastapi import FastAPI, HTTPException, Security, Depends, status
import os
import uuid
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

app = FastAPI(title="Multi-Tenant Organization API")

ORG_KEYS = {
    "org-alpha": os.getenv("ORG_ALPHA_KEY"),
    "org-beta": os.getenv("ORG_BETA_KEY"),
}

org_id_header = APIKeyHeader(name="X-Organization-ID", auto_error=False, scheme_name="org-id")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")


def verify_org_access(
    org_id: str = Security(org_id_header),
    api_key: str = Security(api_key_header),
):
    if not org_id or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing organization credentials"
        )
    expected_key = ORG_KEYS.get(org_id)
    if expected_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organization credentials"
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization ID and API key do not match"
        )
    return org_id


employees = []


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(min_length=2, max_length=100)


@app.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(employee: EmployeeCreate, org_id: str = Depends(verify_org_access)):
    for emp in employees:
        if emp["email"] == employee.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee with this email already exists"
            )

    new_employee = {
        "id": str(uuid.uuid4()),
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "org_id": org_id,
    }
    employees.append(new_employee)
    return new_employee


@app.get("/employees")
def list_employees(org_id: str = Depends(verify_org_access)):
    org_employees = [emp for emp in employees if emp["org_id"] == org_id]
    return {"count": len(org_employees), "employees": org_employees}


@app.get("/employees/{employee_id}")
def get_employee(employee_id: str, org_id: str = Depends(verify_org_access)):
    for emp in employees:
        if emp["id"] == employee_id:
            if emp["org_id"] != org_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee not found"
                )
            return emp
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Employee not found"
    )
