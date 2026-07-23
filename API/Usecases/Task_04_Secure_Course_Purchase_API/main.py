from fastapi import FastAPI, HTTPException, Security, status
import os
import uuid
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

app = FastAPI(title="Secure Course Purchase API")

API_KEY = os.getenv("API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return key


COURSES = {
    1: {"name": "Python Masterclass", "price": 499.0},
    2: {"name": "Machine Learning", "price": 799.0},
    3: {"name": "Generative AI", "price": 999.0},
    4: {"name": "Data Science", "price": 699.0},
    5: {"name": "FastAPI Pro", "price": 399.0},
}


COUPONS = {
    "CASH20": 20,
    "STUDENT10": 10,
    "FLAT50": 50,
    "WELCOME15": 15,
}


purchases = {}


class PurchaseRequest(BaseModel):
    student_email: EmailStr
    course_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=5)
    coupon_code: str | None = None


@app.post("/courses/purchase", status_code=status.HTTP_201_CREATED)
def purchase_course(request: PurchaseRequest, key: str = Security(verify_api_key)):
    course = COURSES.get(request.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    unit_price = course["price"]
    total_before_discount = unit_price * request.quantity

    discount_percent = 0
    if request.coupon_code:
        discount_percent = COUPONS.get(request.coupon_code)
        if discount_percent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid coupon code"
            )

    discount_amount = round(total_before_discount * discount_percent / 100, 2)
    final_amount = round(total_before_discount - discount_amount, 2)

    purchase_id = str(uuid.uuid4())

    purchase_record = {
        "purchase_id": purchase_id,
        "student_email": request.student_email,
        "course_id": request.course_id,
        "course_name": course["name"],
        "quantity": request.quantity,
        "unit_price": unit_price,
        "total_before_discount": total_before_discount,
        "coupon_code": request.coupon_code,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "final_amount": final_amount,
        "status": "completed",
    }

    purchases[purchase_id] = purchase_record

    return purchase_record


@app.get("/purchases/{purchase_id}")
def get_purchase(purchase_id: str, key: str = Security(verify_api_key)):
    purchase = purchases.get(purchase_id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    return purchase
