from fastapi import FastAPI, HTTPException, Security, Request  # web framework, error handling, Security DI, request object
import os                                           # read env vars from OS / .env
from pathlib import Path                            # build absolute path to .env
import uuid                                         # generate unique ticket IDs
from enum import Enum                               # strict enum for priority and status (auto 422)
from dotenv import load_dotenv                      # load .env file into os.environ
from fastapi.security import APIKeyHeader           # extract API key from HTTP header
from slowapi import Limiter                         # rate limiter – limits requests per IP
from slowapi.errors import RateLimitExceeded        # exception raised when rate limit hit
from slowapi.util import get_remote_address         # extracts client IP for rate limiting
from slowapi import _rate_limit_exceeded_handler    # built-in JSON handler for 429 responses
from pydantic import BaseModel, EmailStr, Field     # schema validation, email type, field constraints

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Customer Support Ticket API")

CUSTOMER_KEY = os.getenv("CUSTOMER_KEY")
STAFF_KEY = os.getenv("STAFF_KEY")

customer_key_header = APIKeyHeader(name="X-Customer-Key", auto_error=False, scheme_name="customer-key")
staff_key_header = APIKeyHeader(name="X-Staff-Key", auto_error=False, scheme_name="staff-key")


def require_customer_key(key: str = Security(customer_key_header)):
    """Guard: rejects if X-Customer-Key header doesn't match CUSTOMER_KEY."""
    if key != CUSTOMER_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


def require_staff_key(key: str = Security(staff_key_header)):
    """Guard: rejects if X-Staff-Key header doesn't match STAFF_KEY."""
    if key != STAFF_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

tickets: dict[str, dict] = {}

# Tuple (email, subject) is hashable → O(1) lookup for duplicate open ticket prevention
open_tickets_by_email_subject: dict[tuple[str, str], str] = {}


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class TicketCreate(BaseModel):
    customer_email: EmailStr
    subject: str = Field(min_length=5, max_length=100)
    description: str = Field(min_length=20, max_length=2000)
    priority: Priority


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    internal_notes: str | None = None


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.post("/tickets", status_code=201)
@limiter.limit("5/hour")
def create_ticket(
    request: Request,
    ticket_data: TicketCreate,
    key: str = Security(require_customer_key),
):
    """Validates input, checks duplicates, then stores ticket with status 'open'."""

    dup_key = (ticket_data.customer_email, ticket_data.subject)
    if dup_key in open_tickets_by_email_subject:  # e.g. ("user@example.com", "Payment failed") already exists?
        raise HTTPException(
            status_code=409,
            detail="An open ticket with this email and subject already exists"
        )

    ticket_id = str(uuid.uuid4())

    ticket = {
        "ticket_id": ticket_id,
        "customer_email": ticket_data.customer_email,
        "subject": ticket_data.subject,
        "description": ticket_data.description,
        "priority": ticket_data.priority.value,
        "status": TicketStatus.open.value,
        "internal_notes": None,
    }

    tickets[ticket_id] = ticket
    open_tickets_by_email_subject[dup_key] = ticket_id

    return {
        "ticket_id": ticket_id,
        "customer_email": ticket_data.customer_email,
        "subject": ticket_data.subject,
        "description": ticket_data.description,
        "priority": ticket_data.priority.value,
        "status": TicketStatus.open.value,
    }


@app.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    key: str = Security(require_customer_key),
):
    """Returns ticket data without internal_notes — customers must not see staff notes."""
    ticket = tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    return {
        "ticket_id": ticket["ticket_id"],
        "customer_email": ticket["customer_email"],
        "subject": ticket["subject"],
        "description": ticket["description"],
        "priority": ticket["priority"],
        "status": ticket["status"],
    }


@app.patch("/tickets/{ticket_id}")
def update_ticket_status(
    ticket_id: str,
    status_data: TicketStatusUpdate,
    key: str = Security(require_staff_key),
):
    """Staff-only: updates ticket status and optionally adds internal notes."""
    ticket = tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    ticket["status"] = status_data.status.value

    if status_data.internal_notes is not None:      # only update notes if staff actually sent one
        ticket["internal_notes"] = status_data.internal_notes

    if status_data.status == TicketStatus.closed:     # remove from open index so customer can re-open with same subject later
        dup_key = (ticket["customer_email"], ticket["subject"])
        open_tickets_by_email_subject.pop(dup_key, None)

    return ticket
