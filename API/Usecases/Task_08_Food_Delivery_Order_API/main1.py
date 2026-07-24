from fastapi import FastAPI, HTTPException, Security, Request  # web framework, error handling, Security DI, request object
import os                                           # read env vars from OS / .env
from pathlib import Path                            # build absolute path to .env
import uuid                                         # generate unique order IDs
from enum import Enum                               # strict status enum (only allowed values pass)
from dotenv import load_dotenv                      # load .env file into os.environ
from fastapi.security import APIKeyHeader           # extract API key from HTTP header
from slowapi import Limiter                         # rate limiter – limits requests per IP
from slowapi.errors import RateLimitExceeded        # exception raised when rate limit hit
from slowapi.util import get_remote_address         # extracts client IP for rate limiting
from slowapi import _rate_limit_exceeded_handler    # built-in JSON handler for 429 responses
from pydantic import BaseModel, EmailStr, Field     # schema validation, email type, field constraints

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Food Delivery Order API")

USER_KEY = os.getenv("USER_KEY")
ADMIN_KEY = os.getenv("ADMIN_KEY")

user_key_header = APIKeyHeader(name="X-User-Key", auto_error=False, scheme_name="user-key")
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False, scheme_name="admin-key")


def require_user_key(key: str = Security(user_key_header)):
    """Guard: rejects request if X-User-Key header doesn't match USER_KEY."""
    if key != USER_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


def require_admin_key(key: str = Security(admin_key_header)):
    """Guard: rejects request if X-Admin-Key header doesn't match ADMIN_KEY."""
    if key != ADMIN_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


RESTAURANTS = {
    1: {
        "name": "Pizza Palace",
        "menu": {
            101: {"name": "Margherita",       "price": 12.99},
            102: {"name": "Pepperoni",        "price": 14.99},
            103: {"name": "Farmhouse",        "price": 15.99},
        },
    },
    2: {
        "name": "Burger Barn",
        "menu": {
            201: {"name": "Classic Burger",   "price": 9.99},
            202: {"name": "Cheese Burger",    "price": 10.99},
            203: {"name": "Veggie Burger",    "price": 8.99},
        },
    },
    3: {
        "name": "Sushi Spot",
        "menu": {
            301: {"name": "California Roll",  "price": 15.99},
            302: {"name": "Salmon Nigiri",    "price": 18.99},
            303: {"name": "Dragon Roll",      "price": 21.99},
        },
    },
}

orders = {}


class OrderStatus(str, Enum):
    placed = "placed"
    accepted = "accepted"
    preparing = "preparing"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderItem(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    customer_email: EmailStr
    restaurant_id: int
    items: list[OrderItem] = Field(min_length=1)


class StatusUpdate(BaseModel):
    status: OrderStatus


@app.get("/health")
def health_check():
    """Returns a simple health status to confirm the API is running."""
    return {"status": "running", "message": "API is running"}


@app.post("/orders", status_code=201)
@limiter.limit("10/minute")
def place_order(request: Request, order_data: OrderCreate):
    """Validates restaurant + items, then stores the order with status 'placed'."""
    restaurant = RESTAURANTS.get(order_data.restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found"
        )

    resolved_items = []
    for item in order_data.items:
        menu_item = restaurant["menu"].get(item.item_id)
        if menu_item is None:
            raise HTTPException(
                status_code=400,
                detail=f"Item {item.item_id} does not belong to {restaurant['name']}"
            )
        resolved_items.append({
            "item_id": item.item_id,
            "name": menu_item["name"],
            "price": menu_item["price"],
            "quantity": item.quantity,
        })

    order_id = str(uuid.uuid4())

    orders[order_id] = {
        "order_id": order_id,
        "customer_email": order_data.customer_email,
        "restaurant_id": order_data.restaurant_id,
        "restaurant_name": restaurant["name"],
        "items": resolved_items,
        "status": OrderStatus.placed.value,
    }

    return {
        "message": "Order placed successfully",
        "order_id": order_id,
    }


@app.get("/orders/{order_id}")
def get_order(order_id: str, key: str = Security(require_user_key)):
    """Returns the full order data for a given order_id (user-auth required)."""
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    return order


@app.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    status_data: StatusUpdate,
    key: str = Security(require_admin_key),
):
    """Updates order status (admin-only). Enum auto-rejects invalid values as 422."""
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    order["status"] = status_data.status.value

    return {
        "message": "Order status updated",
        "order_id": order_id,
        "status": order["status"],
    }
