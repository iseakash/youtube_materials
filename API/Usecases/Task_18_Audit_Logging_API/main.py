"""
Audit Logging API — records all sensitive admin actions with automatic sensitive-field redaction.

Key imports explained:
- APIKeyHeader: extracts X-Admin-Key header for Security() registration in Swagger
- Security(): registers the admin key scheme in OpenAPI so Swagger UI shows an Authorize button
- datetime(timezone.utc): generates immutable timestamps in UTC for audit trail integrity
- Field(min_length): enforces string constraints at the Pydantic boundary
"""

from fastapi import FastAPI, HTTPException, Security, Depends, status
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

app = FastAPI(title="Audit Logging API")

ADMIN_KEY = os.getenv("ADMIN_KEY")
ADMIN_IDENTITY = os.getenv("ADMIN_IDENTITY")

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_admin_key(key: str = Security(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin key"
        )
    return key


users = []
audit_logs = []

SENSITIVE_FIELDS = {"password", "api_key", "secret", "token"}


def sanitize(data: dict) -> dict:
    return {k: v for k, v in data.items() if k.lower() not in SENSITIVE_FIELDS}


def log_action(action: str, admin: str, resource: str, result: str, details: dict | None = None):
    audit_logs.append({
        "action": action,
        "admin": admin,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resource": resource,
        "result": result,
        "details": sanitize(details) if details else None,
    })


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)


@app.post("/admin/users", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, key: str = Security(require_admin_key)):
    for existing in users:
        if existing["email"] == user.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )

    user_id = str(uuid.uuid4())
    new_user = {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "password": user.password,
    }
    users.append(new_user)

    log_action("created", ADMIN_IDENTITY, user_id, "success", new_user)

    return {
        "id": user_id,
        "name": user.name,
        "email": user.email,
    }


@app.delete("/admin/users/{user_id}")
def delete_user(user_id: str, key: str = Security(require_admin_key)):
    for index, existing in enumerate(users):
        if existing["id"] == user_id:
            removed = users.pop(index)
            log_action("deleted", ADMIN_IDENTITY, user_id, "success", removed)
            return {"message": "User deleted successfully", "user_id": user_id}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


@app.get("/admin/audit-logs")
def get_audit_logs(key: str = Security(require_admin_key)):
    return {"count": len(audit_logs), "logs": audit_logs}
