# 20 FastAPI Real-World Tasks

## General instructions

For every task, students should:

- Use FastAPI
- Use Pydantic models
- Store data in a Python dictionary or list unless a database is specifically requested
- Add proper HTTP status codes
- Add validation
- Add safe error messages
- Test APIs using Swagger UI or Postman
- Submit the GitHub repository link
- Submit a short demonstration video
- Add a README.md file explaining how to run the project
- Never hard-code secrets inside the Python file

# Task 1: Secure Student Registration API

## Scenario

A training institute wants an API where students can register for a course. The institute is receiving fake registrations, invalid email addresses, and unrealistic ages.

## Requirements

Create a POST /students/register endpoint.

The API should accept:

```
{
  "name": "Rahul Kumar",
  "email": "rahul@example.com",
  "age": 24,
  "course": "FastAPI"
}
```
Validation rules:

- Name must contain between 2 and 50 characters
- Email must be valid
- Age must be between 16 and 65
- Course name must contain between 2 and 100 characters
- Duplicate email registration must not be allowed
- Return status code 201 after successful registration
- Return status code 409 if the email already exists
- Protect the endpoint using an API key
## Security challenge

The API key must come from a .env file.


# Task 2: Employee Attendance API with Role-Based Access

## Scenario

A company wants employees to mark attendance, but only managers should be able to view the attendance of all employees.

## Requirements

Create these endpoints:

```
POST /attendance/check-in
GET /attendance/my
GET /attendance/all
```
Rules:

- Employees can check in only once per day
- An employee can view only their own attendance
- A manager can view everyone’s attendance
- Use two different headers:
```
X-Employee-Key
X-Manager-Key
```
- Return 403 Forbidden when an employee tries to access the manager endpoint
- Store the check-in date and time
## Security challenge

Do not expose the valid manager key in any error response.


# Task 3: Online Examination Submission API

## Scenario

An online examination platform wants students to submit answers. Students are trying to submit the exam multiple times and send extremely large text responses.

## Requirements

Create:

```
POST /exam/submit
GET /exam/result/{student_id}
```
The submission should contain:

```
{
  "student_id": 101,
  "exam_id": 501,
  "answers": [
    {
      "question_id": 1,
      "answer": "FastAPI is a Python framework"
    }
  ]
}
```
Rules:

- A student can submit an exam only once
- Each answer must contain no more than 500 characters
- The request must contain at least one answer
- Maximum 100 answers per submission
- Result endpoint must require an API key
- Return 409 for duplicate submission
- Return 404 when no result exists
## Security challenge

Apply a rate limit of three exam submissions per minute per IP address.


# Task 4: Secure Course Purchase API

## Scenario

An EdTech platform wants an API for purchasing courses. Attackers are trying to send negative prices and fake discount values.

## Requirements

Create:

```
POST /courses/purchase
GET /purchases/{purchase_id}
```
Request example:

```
{
  "student_email": "student@example.com",
  "course_id": 10,
  "quantity": 1,
  "coupon_code": "EURON20"
}
```
Rules:

- Course price must come from server-side data
- The client must not send the final price
- Quantity must be between 1 and 5
- Accept only valid coupon codes
- Calculate the final amount on the server
- Create a unique purchase ID
- Return 201 after purchase
- Return 400 for an invalid coupon
- Protect the purchase endpoint with an API key
## Security challenge

Students must explain why the price should not be trusted when sent by the frontend.


# Task 5: Password Login API with Brute-Force Protection

## Scenario

A learning portal is experiencing repeated login attempts from attackers trying to guess passwords.

## Requirements

Create:

```
POST /login
```
Request:

```
{
  "email": "admin@example.com",
  "password": "secret123"
}
```
Rules:

- Allow only five login attempts per minute per IP
- Use a generic message for invalid credentials
- Do not say whether the email or password was incorrect
- Return 401 for invalid credentials
- Return 429 when the rate limit is exceeded
- Return a simple token after a successful login
## Security challenge

The password and generated token must not be printed in logs.


# Task 6: Banking Money Transfer API

## Scenario

A banking application wants customers to transfer money between accounts.

## Requirements

Create:

```
POST /accounts/transfer
GET /accounts/{account_id}/balance
```
Transfer request:

```
{
  "from_account": 1001,
  "to_account": 1002,
  "amount": 5000
}
```
Rules:

- Amount must be greater than zero
- Sender and receiver accounts cannot be the same
- Sender must have sufficient balance
- Maximum transfer amount is ₹1,00,000
- Every transaction must have a transaction ID
- Return 400 for insufficient balance
- Return 404 if an account does not exist
- Protect transfer with a private API key
- Apply a rate limit of five transfers per minute
## Security challenge

The balance should update only when all validations pass.


# Task 7: Hospital Appointment Booking API

## Scenario

A hospital wants an appointment booking API. Patients are booking the same doctor and time slot multiple times.

## Requirements

Create:

```
POST /appointments
GET /appointments/{appointment_id}
DELETE /appointments/{appointment_id}
```
Appointment data:

```
{
  "patient_name": "Anita Sharma",
  "patient_email": "anita@example.com",
  "doctor_id": 15,
  "appointment_date": "2026-07-25",
  "time_slot": "10:30"
}
```
Rules:

- Appointment date cannot be in the past
- The doctor must exist
- The slot must be available
- The same doctor cannot have two appointments in the same slot
- Patient email must be valid
- Cancellation requires an API key
- Return 409 if the slot is already booked
## Security challenge

Do not expose other patients’ appointment data.


# Task 8: Food Delivery Order API

## Scenario

A food delivery platform wants customers to place orders. Some users are sending empty orders, invalid quantities, and fake restaurant IDs.

## Requirements

Create:

```
POST /orders
GET /orders/{order_id}
PATCH /orders/{order_id}/status
```
Rules:

- Order must contain at least one item
- Each item quantity must be between 1 and 10
- Restaurant must exist
- All items must belong to the selected restaurant
- Customer may view their own order
- Only an admin can change the order status
- Allowed statuses:
```
placed
accepted
preparing
out_for_delivery
delivered
cancelled
```
## Security challenge

Prevent invalid status values using Literal or an enum.


# Task 9: E-Commerce Inventory Protection API

## Scenario

An online store has limited stock. Multiple users may attempt to purchase the last available item.

## Requirements

Create:

```
GET /products
POST /products/{product_id}/purchase
```
Rules:

- Product ID must be a positive integer
- Quantity must be between 1 and 20
- Reject the request if stock is insufficient
- Reduce stock only after successful validation
- Return 409 if stock is insufficient
- Apply a rate limit of ten purchases per minute
- Protect the purchase endpoint using an API key
## Security challenge

The stock must never become negative.


# Task 10: File Upload Metadata API

## Scenario

A student portal allows assignment uploads. Students are trying to upload unsupported file types and extremely large files.

## Requirements

Create:

```
POST /assignments/upload
GET /assignments/{submission_id}
```
Rules:

- Accept only PDF, DOCX, and ZIP files
- Maximum file size should be 5 MB
- Student ID and assignment ID are required
- A student can submit only once per assignment
- Generate a unique submission ID
- Return 413 for oversized files
- Return 415 for unsupported file types
- Protect upload using an API key
## Security challenge

Do not use the original filename directly when saving the file.


# Task 11: Customer Support Ticket API

## Scenario

A SaaS company wants customers to raise support tickets. Some users are sending huge descriptions and repeatedly creating duplicate tickets.

## Requirements

Create:

```
POST /tickets
GET /tickets/{ticket_id}
PATCH /tickets/{ticket_id}
```
Ticket fields:

```
{
  "customer_email": "user@example.com",
  "subject": "Payment failed",
  "description": "My payment was deducted but access was not activated.",
  "priority": "high"
}
```
Rules:

- Subject must be between 5 and 100 characters
- Description must be between 20 and 2000 characters
- Priority must be low, medium, high, or critical
- Prevent duplicate open tickets with the same email and subject
- Only support staff can update ticket status
- Apply a rate limit of five tickets per hour per user
## Security challenge

Internal support notes must not be returned to the customer.


# Task 12: API Usage Plan and Subscription Limiting

## Scenario

A software company provides three API plans:

```
Free
Pro
Enterprise
```
Each plan has a different request limit.

## Requirements

Create:

```
GET /data
```
Users send:

```
X-API-Key
```
Rules:

- Free plan: 5 requests per minute
- Pro plan: 20 requests per minute
- Enterprise plan: 100 requests per minute
- Identify the plan using the API key
- Return the user’s current plan in the response
- Return 401 for unknown API keys
- Return 429 when the plan limit is exceeded
## Security challenge

Rate limiting must happen per API key, not only per IP address.


# Task 13: Secure Password Reset Request API

## Scenario

A user forgets their password and requests a password-reset link. Attackers are using this endpoint to identify registered email addresses.

## Requirements

Create:

```
POST /password-reset/request
POST /password-reset/confirm
```
Rules:

- Request endpoint accepts an email address
- Always return the same message whether the email exists or not
- Generate a reset token only for registered users
- Token must expire after a limited time
- Password must have at least eight characters
- Reset token can be used only once
- Apply strict rate limiting
## Security challenge

The response must not reveal whether the email exists in the system.


# Task 14: Coupon Management API

## Scenario

An e-commerce administrator wants to create discount coupons, while customers can only validate coupons.

## Requirements

Create:

```
POST /admin/coupons
GET /coupons/validate
DELETE /admin/coupons/{coupon_code}
```
Rules:

- Admin endpoints require an admin API key
- Coupon discount must be between 1% and 80%
- Expiry date must be in the future
- Coupon code must be unique
- Validation endpoint takes coupon code and order value
- Coupon may have a minimum order value
- Expired coupons should return a controlled error
- Return 403 for non-admin access
## Security challenge

Customers must never be able to create or delete coupons.


# Task 15: Delivery Tracking API with CORS

## Scenario

A logistics company has a customer website and a separate internal admin dashboard.

Customer website:

```
https://track.company.com
```
Admin dashboard:

```
https://admin.company.com
```
## Requirements

Create:

```
GET /tracking/{tracking_id}
PATCH /tracking/{tracking_id}
```
Rules:

- Customer website can call only GET
- Admin dashboard can call GET and PATCH
- Only exact frontend origins should be allowed
- Tracking status must be validated
- Admin update requires an API key
- Return 404 for invalid tracking IDs
## Security challenge

Configure CORS without using:

```
allow_origins=["*"]
```
Students must explain why CORS does not replace authentication.


# Task 16: Multi-Tenant Organization API

## Scenario

A SaaS platform serves multiple companies. Employees from one company must never see data belonging to another company.

## Requirements

Create:

```
POST /employees
GET /employees
GET /employees/{employee_id}
```
Each request should contain:

```
X-Organization-ID
X-API-Key
```
Rules:

- Every employee record belongs to an organization
- An organization can view only its own employees
- The same API key must be mapped to a specific organization
- Return 403 if the organization ID and API key do not match
- Prevent one organization from accessing another organization’s employee ID
- Validate employee email and department
## Security challenge

This task must prevent cross-tenant data leakage.


# Task 17: Webhook Receiver API

## Scenario

A payment gateway sends payment status updates to your FastAPI application through a webhook.

## Requirements

Create:

```
POST /webhooks/payment
```
Example payload:

```
{
  "event_id": "evt_123",
  "payment_id": "pay_501",
  "status": "success",
  "amount": 2999
}
```
Rules:

- Request must contain a webhook secret header
- Reject requests with an invalid secret
- Process the same event_id only once
- Allowed statuses are success, failed, pending, and refunded
- Amount must be positive
- Return quickly after processing
- Store processed event IDs
## Security challenge

Prevent replay attacks by rejecting duplicate event IDs.


# Task 18: Audit Logging API

## Scenario

A company wants to record all sensitive actions performed by administrators.

## Requirements

Create:

```
POST /admin/users
DELETE /admin/users/{user_id}
GET /admin/audit-logs
```
Rules:

- All endpoints require an admin key
- Every create and delete operation must generate an audit log
- Audit log should include:
```
action
admin identity
time
affected resource
result
```
- Sensitive values such as passwords and API keys must not be logged
- Audit logs should not be modifiable
- Return safe error messages
## Security challenge

Create a logging function that automatically removes sensitive fields.


# Task 19: Secure Book Library API

## Scenario

A digital library allows users to borrow books. A user cannot borrow more than three books at a time.

## Requirements

Create:

```
GET /books
POST /books/{book_id}/borrow
POST /books/{book_id}/return
GET /users/{user_id}/borrowed-books
```
Rules:

- Book must exist
- Book must be available before borrowing
- A user can borrow a maximum of three books
- The same book cannot be borrowed by two users
- Only the correct user can return their borrowed book
- All borrow and return actions require authentication
- Rate limit borrowing attempts
## Security challenge

Ensure all validations complete before changing the book’s availability.


# Task 20: Complete Secure Learning Management System API

## Scenario

Build a small Learning Management System for students, instructors, and administrators.

## Required roles

```
student
instructor
admin
```
## Required endpoints

```
POST /auth/login
POST /students/register
POST /courses
GET /courses
GET /courses/{course_id}
POST /courses/{course_id}/enroll
GET /students/{student_id}/courses
POST /courses/{course_id}/lessons
DELETE /courses/{course_id}
GET /admin/audit-logs
```
## Business rules

- Anyone may view the public course list
- Only students can enroll
- Only instructors can create lessons
- Only instructors and admins can create courses
- Only admins can delete courses
- A student cannot enroll in the same course twice
- A course may have a maximum number of seats
- Course title must be unique
- Student email must be unique
- Course creation and deletion must generate audit logs
## Security requirements

The project must contain:

- API-key authentication or token-based authentication
- Role-based authorization
- Rate limiting
- Exact CORS origins
- Pydantic validation
- Environment variables
- Safe global exception handling
- Custom 404, 401, 403, 409, and 429 responses
- Separate public and private endpoints
- Prevention of duplicate requests
- No secrets inside source code
- No stack traces returned to API users
## Final testing requirements

Students should demonstrate:

- Successful student registration
- Invalid email rejection
- Duplicate email rejection
- Successful login
- Invalid login rejection
- Rate-limit rejection
- Student attempting an admin action
- Instructor creating a course
- Student enrolling in a course
- Duplicate enrollment rejection
- Course seat limit rejection
- Safe error handling
- Invalid API-key rejection
- CORS configuration
- Secret loading from .env
