"""
Webhook Receiver API — securely receives payment status updates.

Key imports explained:
- APIKeyHeader: extracts X-Webhook-Secret header for Security() registration in Swagger
- Enum: restricts payment status to allowed values (success, failed, pending, refunded)
- Field(gt=0): enforces positive amount at the Pydantic boundary
- Security(): registers the webhook secret scheme in OpenAPI so Swagger UI shows an Authorize button
"""

from fastapi import FastAPI, HTTPException, Security, Depends, status
import os
from enum import Enum
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Webhook Receiver API")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

webhook_header = APIKeyHeader(name="X-Webhook-Secret", auto_error=False)


def verify_webhook_secret(key: str = Security(webhook_header)):
    if key != WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret"
        )
    return key


processed_events = set()


class PaymentStatus(str, Enum):
    success = "success"
    failed = "failed"
    pending = "pending"
    refunded = "refunded"


class WebhookPayload(BaseModel):
    event_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    status: PaymentStatus
    amount: float = Field(gt=0)


@app.post("/webhooks/payment")
def handle_webhook(payload: WebhookPayload, key: str = Security(verify_webhook_secret)):
    if payload.event_id in processed_events:
        return {"message": "Event already processed"}

    processed_events.add(payload.event_id)

    return {
        "message": "Webhook received",
        "event_id": payload.event_id,
        "payment_id": payload.payment_id,
        "status": payload.status.value,
        "amount": payload.amount,
    }
