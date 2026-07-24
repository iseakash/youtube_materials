from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Delivery Tracking API with CORS")

# CORS — only exact frontend origins allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "PATCH"],
    allow_headers=["content-type", "X-Admin-Key"],
)

ADMIN_KEY = os.getenv("ADMIN_KEY")

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_admin_key(key: str = Depends(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


class TrackingStatus(str, Enum):
    created = "created"
    picked_up = "picked_up"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    failed = "failed"


class StatusUpdate(BaseModel):
    status: TrackingStatus


packages = {
    "TKT001": {
        "tracking_id": "TKT001",
        "status": "in_transit",
        "origin": "New York, NY",
        "destination": "Los Angeles, CA",
        "last_updated": "2025-07-24T10:30:00Z",
    },
    "TKT002": {
        "tracking_id": "TKT002",
        "status": "out_for_delivery",
        "origin": "Chicago, IL",
        "destination": "Austin, TX",
        "last_updated": "2025-07-24T14:00:00Z",
    },
}


@app.get("/tracking/{tracking_id}")
def get_tracking(tracking_id: str):
    """Customer tracking — no auth required."""
    pkg = packages.get(tracking_id)
    if pkg is None:
        raise HTTPException(
            status_code=404,
            detail="Tracking ID not found"
        )
    return pkg


@app.patch("/tracking/{tracking_id}", dependencies=[Depends(require_admin_key)])
def update_tracking(tracking_id: str, status_data: StatusUpdate):
    """Admin-only status update — requires X-Admin-Key."""
    pkg = packages.get(tracking_id)
    if pkg is None:
        raise HTTPException(
            status_code=404,
            detail="Tracking ID not found"
        )

    pkg["status"] = status_data.status.value
    pkg["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "message": "Status updated successfully",
        "tracking_id": tracking_id,
        "status": pkg["status"],
        "last_updated": pkg["last_updated"],
    }
