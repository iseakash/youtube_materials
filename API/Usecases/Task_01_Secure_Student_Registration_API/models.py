from pydantic import BaseModel, EmailStr, Field


class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    age: int = Field(ge=16, le=100)
    course: str = Field(min_length=2, max_length=500)
