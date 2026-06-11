from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Portfolio API")

# BaseModel is a class from the Pydantic library that provides data validation and parsing.
# It automatically validates incoming data against those types. If the data is invalid, Pydantic will raise an error.
# When you create a class that inherits from BaseModel, you can define fields with specific types (like str, int, etc.).
class Contact(BaseModel):
    name: str
    email: str
    message: str

contacts_db = []

@app.get("/")
def read_root():
    return {"message": "Portfolio API is running"}

@app.get("/health")
def read_health():
    return {"status": "healthy"}

@app.post("/contact")
def submit_contact(contact: Contact):
    contacts_db.append({
        "name": contact.name,
        "email": contact.email,
        "message": contact.message,
        "timestamp": datetime.now().isoformat()
    })
    return {"message": f"Thanks {contact.name}, we'll be in touch!"}