from fastapi import FastAPI, HTTPException, Security, Request
import os
import uuid
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Banking Money Transfer API")

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


ACCOUNTS = {
    "123456781": {"name": "Alice",   "balance": 50000.0},
    "123456782": {"name": "Bob",     "balance": 30000.0},
    "123456783": {"name": "Charlie", "balance": 100000.0},
}

transactions = []


class TransferRequest(BaseModel):
    from_account: str = Field(min_length=8, max_length=18, pattern=r"^\d+$")
    to_account: str = Field(min_length=8, max_length=18, pattern=r"^\d+$")
    amount: float = Field(gt=0, le=100000)


@app.post("/accounts/transfer")
@limiter.limit("5/minute")
def transfer(request: Request, transfer_data: TransferRequest, key: str = Security(verify_api_key)):
    sender = ACCOUNTS.get(transfer_data.from_account)
    if sender is None:
        raise HTTPException(
            status_code=404,
            detail="Sender account not found"
        )

    receiver = ACCOUNTS.get(transfer_data.to_account)
    if receiver is None:
        raise HTTPException(
            status_code=404,
            detail="Receiver account not found"
        )

    if transfer_data.from_account == transfer_data.to_account:
        raise HTTPException(
            status_code=400,
            detail="Sender and receiver accounts must be different"
        )

    if sender["balance"] < transfer_data.amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance"
        )

    sender["balance"] -= transfer_data.amount
    receiver["balance"] += transfer_data.amount

    transaction_id = str(uuid.uuid4())

    transaction_record = {
        "transaction_id": transaction_id,
        "from_account": transfer_data.from_account,
        "to_account": transfer_data.to_account,
        "amount": transfer_data.amount,
        "status": "completed",
    }
    transactions.append(transaction_record)

    return {
        "message": "Transfer successful",
        "transaction_id": transaction_id,
    }


@app.get("/accounts/{account_id}/balance")
def get_balance(account_id: str, key: str = Security(verify_api_key)):
    account = ACCOUNTS.get(account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Account not found"
        )

    return {
        "account_id": account_id,
        "name": account["name"],
        "balance": account["balance"],
    }


@app.get("/health")
def health_check():
    return {
        "status": "running",
        "message": "API is running"
    }
