from fastapi import FastAPI, HTTPException, Security, Query  # web framework, error handling, Security DI, query params
from typing import Annotated                         # PEP 593 — type + metadata for query params
import os                                           # read env vars from OS / .env
from pathlib import Path                            # build absolute path to .env
from datetime import date                           # current date for expiry validation
from dotenv import load_dotenv                      # load .env file into os.environ
from fastapi.security import APIKeyHeader           # extract API key from HTTP header
from pydantic import BaseModel, Field               # schema validation, field constraints

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Coupon Management API")

ADMIN_KEY = os.getenv("ADMIN_KEY")
CUSTOMER_KEY = os.getenv("CUSTOMER_KEY")

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False, scheme_name="admin-key")
customer_key_header = APIKeyHeader(name="X-Customer-Key", auto_error=False, scheme_name="customer-key")


def require_admin(key: str = Security(admin_key_header)):
    """Rejects with 403 if customer key used, 401 if missing/invalid, returns key on success."""
    if key == CUSTOMER_KEY:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    if key != ADMIN_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


def require_customer(key: str = Security(customer_key_header)):
    """Rejects if X-Customer-Key header doesn't match CUSTOMER_KEY."""
    if key != CUSTOMER_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


coupons: dict[str, dict] = {
    "DISCOUNT30": {
        "code": "DISCOUNT30",
        "discount_percent": 30,
        "expiry": "2026-12-31",
        "min_order_value": 500.0,
        "is_active": True,
    },
    "SAVE20": {
        "code": "SAVE20",
        "discount_percent": 20,
        "expiry": "2025-12-31",
        "min_order_value": 500.0,
        "is_active": True,
    },
    "WELCOME10": {
        "code": "WELCOME10",
        "discount_percent": 10,
        "expiry": "2026-06-30",
        "min_order_value": None,
        "is_active": True,
    },
}


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z0-9_]+$")
    discount_percent: int = Field(ge=1, le=80)
    expiry: date
    min_order_value: float | None = Field(default=None, ge=0)


class CouponValidateQuery(BaseModel):
    code: str
    order_value: float = Field(gt=0)


@app.get("/health")
def health_check():
    return {"status": "running", "message": "API is running"}


@app.post("/admin/coupons", status_code=201)
def create_coupon(
    coupon_data: CouponCreate,
    key: str = Security(require_admin),
):
    """Creates a new coupon after validating uniqueness, discount range, and future expiry."""

    if coupon_data.code in coupons:
        raise HTTPException(
            status_code=409,
            detail="Coupon code already exists"
        )

    if coupon_data.expiry <= date.today():
        raise HTTPException(
            status_code=400,
            detail="Expiry date must be in the future"
        )

    coupon = {
        "code": coupon_data.code,
        "discount_percent": coupon_data.discount_percent,
        "expiry": coupon_data.expiry.isoformat(),
        "min_order_value": coupon_data.min_order_value,
        "is_active": True,
    }

    coupons[coupon_data.code] = coupon

    return {
        "message": "Coupon created successfully",
        "coupon": coupon,
    }


@app.get("/coupons/validate")
def validate_coupon(
    code: Annotated[str, Query(min_length=1)],
    order_value: Annotated[float, Query(gt=0)],
    key: str = Security(require_customer),
):
    """Validates a coupon code against an order value — checks active, expiry, and min order."""

    coupon = coupons.get(code)
    if coupon is None:
        raise HTTPException(
            status_code=404,
            detail="Coupon not found"
        )

    if not coupon["is_active"]:
        raise HTTPException(
            status_code=400,
            detail="Coupon is no longer active"
        )

    expiry = date.fromisoformat(coupon["expiry"])
    if expiry < date.today():
        raise HTTPException(
            status_code=400,
            detail="Coupon has expired"
        )

    min_val = coupon["min_order_value"]
    if min_val is not None and order_value < min_val:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order value of {min_val} not met"
        )

    discount_amount = round(order_value * coupon["discount_percent"] / 100, 2)
    final_amount = round(order_value - discount_amount, 2)

    return {
        "valid": True,
        "code": code,
        "discount_percent": coupon["discount_percent"],
        "discount_amount": discount_amount,
        "original_amount": order_value,
        "final_amount": final_amount,
    }


@app.delete("/admin/coupons/{coupon_code}")
def delete_coupon(
    coupon_code: str,
    key: str = Security(require_admin),
):
    """Deletes a coupon by code. Admin-only."""

    coupon = coupons.get(coupon_code)
    if coupon is None:
        raise HTTPException(
            status_code=404,
            detail="Coupon not found"
        )

    coupons.pop(coupon_code)

    return {"message": "Coupon deleted successfully"}
