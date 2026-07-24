from fastapi import FastAPI, HTTPException, Depends, Request
import os
from pathlib import Path
import threading
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="E-Commerce Inventory Protection API")

API_KEY = os.getenv("API_KEY")

# APIKeyHeader extracts the API key from the X-API-Key header sent by the client.
# auto_error=False means we handle missing key ourselves instead of letting FastAPI auto-reject.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="api-key")


def require_api_key(key: str = Depends(api_key_header)):
    """Guard: rejects the request if X-API-Key header doesn't match the stored API_KEY."""
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Thread lock prevents race conditions when multiple purchase requests arrive simultaneously,
# ensuring stock can never go negative even under concurrent access.
stock_lock = threading.Lock()

products = {
    1: {"name": "Laptop",   "price": 999.99, "stock": 10},
    2: {"name": "Mouse",    "price": 25.99,  "stock": 50},
    3: {"name": "Keyboard", "price": 49.99,  "stock": 5},
    4: {"name": "Monitor",  "price": 199.99, "stock": 2},
}


class PurchaseRequest(BaseModel):
    quantity: int = Field(ge=1, le=20)


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.get("/products")
def list_products():
    """Returns all products with their current stock levels. Requires no authentication."""
    return {"products": [
        {"id": pid, **pdata} for pid, pdata in products.items()
    ]}


@app.post("/products/{product_id}/purchase")
@limiter.limit("10/minute")
def purchase_product(
    request: Request,
    product_id: int,
    purchase_data: PurchaseRequest,
    key: str = Depends(require_api_key),
):
    """Validates stock availability, then atomically reduces stock using a thread lock."""
    product = products.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    quantity = purchase_data.quantity

    # Acquire lock so only one request can check-and-reduce stock at a time.
    with stock_lock:
        # Everything inside this block is entirely thread-safe
        if product["stock"] < quantity:
            raise HTTPException(
                status_code=409,
                detail="Insufficient stock"
            )

        product["stock"] -= quantity

    return {
        "message": "Purchase successful",
        "product_id": product_id,
        "product_name": product["name"],
        "quantity_purchased": quantity,
        "remaining_stock": product["stock"],
    }
