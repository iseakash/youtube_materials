from fastapi import FastAPI, Request                 # For web framework and Request for parsing JSON body
from fastapi.middleware.cors import CORSMiddleware   # To allow cross-origin requests from the frontend container
from fastapi.responses import JSONResponse           # To return responses with specific status codes
import psycopg2                                      # For PostgreSQL database connection
from psycopg2.extras import RealDictCursor           # To return query results as dictionaries
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
import time

# Create a FastAPI application instance
app = FastAPI()

# Enable CORS — it is like telling the browser's security guard:
# It is okay for the frontend website (localhost:3000) to talk to this backend API (localhost:5000).
# Without this, the browser would block the request for safety."
app.add_middleware(
    CORSMiddleware,
    # Allow all origins ("*") — works for local development.
    allow_origins=["*"],  # For production, restrict this to specific domains like ["http://localhost"].
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all request headers (Content-Type, Authorization, etc.)
)


def get_db_connection():
    # Establish and return a connection to the PostgreSQL database using config values
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn


def init_db():
    # Retry connecting to the database up to 30 times (handles race condition with DB container startup)
    for i in range(30):
        try:
            # conn = the phone line to the database (the connection)
            # cur  = the person speaking on that phone (the cursor)
            # You need both: conn keeps the line open, cur actually sends queries and gets results.
            conn = get_db_connection()
            cur = conn.cursor()

            # Create the employees table if it does not already exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id SERIAL PRIMARY KEY,  -- Auto-incrementing unique ID
                    name VARCHAR(100) NOT NULL,  -- Employee full name (required)
                    email VARCHAR(100) UNIQUE NOT NULL,  -- Employee email (required, must be unique)
                    department VARCHAR(100),  -- Department name (optional)
                    position VARCHAR(100),  -- Job position / title (optional)
                    salary NUMERIC(10,2),  -- Employee salary with 2 decimal places (optional)
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Auto-set creation timestamp
                )
            """)
            conn.commit()  # Save the changes permanently to the database & make it visible to everyone
            cur.close()  # Close the cursor
            conn.close()  # Close the database connection
            print("Database initialized successfully")
            return  # Exit the function once the database is ready
        except Exception as e:
            # If connection fails (DB not ready yet), wait 2 seconds and retry
            print(f"Waiting for database... ({e})")
            time.sleep(2)
    print("Failed to connect to database after 30 attempts")


@app.get("/api/employees")
def get_employees():
    # Fetch all employees from the database ordered by ID
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)  # Cursor returns rows as dictionaries
    cur.execute("SELECT * FROM employees ORDER BY id")  # Send query request for all employees sorted by ID
    employees = cur.fetchall()  # Retrieve all matching rows prepared by database after query execution
    cur.close()
    conn.close()
    return employees  # Return the employee list as JSON (FastAPI auto-converts)


@app.get("/api/employees/{id}")
def get_employee(id: int):
    # Fetch a single employee by their ID
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM employees WHERE id = %s", (id,))  # Query employee by ID (parameterized query prevents SQL injection)
    employee = cur.fetchone()  # Get the first matching row (or None if not found)
    cur.close()
    conn.close()
    if employee:
        return employee  # Return employee as JSON if found
    return JSONResponse(content={"error": "Employee not found"}, status_code=404)


@app.post("/api/employees")
async def create_employee(request: Request):        # async: good, reads body without blocking
    # Create a new employee from JSON request body
    # await is just saying: "hold on, let this finish first, then do the next thing." 
    data = await request.json()  # Parse the incoming JSON request body, await to not block the server while waiting
    name = data.get("name")
    email = data.get("email")
    department = data.get("department")
    position = data.get("position")
    salary = data.get("salary")

    # Validate that required fields (name and email) are provided
    if not name or not email:
        return JSONResponse(content={"error": "Name and email are required"}, status_code=400)

    conn = get_db_connection()  # Open a new DB connection
    cur = conn.cursor(cursor_factory=RealDictCursor)  # Cursor returns rows as dictionaries
    try:
        # Insert the new employee into the database and return the created record
        cur.execute(
            """INSERT INTO employees (name, email, department, position, salary)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (name, email, department, position, salary)
        )   # RETURNING * tells PostgreSQL: "After you insert, immediately hand me back the complete row including anything the database auto-generated."

        conn.commit()
        employee = cur.fetchone()
        return employee, 201  # Return the created employee with HTTP 201 (Created)
    except psycopg2.errors.UniqueViolation:
        # Handle duplicate email error (email column has UNIQUE constraint)
        conn.rollback()  # Clears the failed transaction
        return JSONResponse(content={"error": "Email already exists"}, status_code=409)
    finally:
        cur.close()
        conn.close()


@app.put("/api/employees/{id}")
async def update_employee(id: int, request: Request):
    # Update an existing employee by ID with data from JSON request body
    data = await request.json()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # First check if the employee exists
    cur.execute("SELECT * FROM employees WHERE id = %s", (id,))
    if not cur.fetchone():  # If no employee found with that ID
        cur.close()
        conn.close()
        return JSONResponse(content={"error": "Employee not found"}, status_code=404)

    # Update all fields for the employee with the given ID
    cur.execute(
        """UPDATE employees SET name = %s, email = %s, department = %s,
           position = %s, salary = %s WHERE id = %s RETURNING *""",
        (
            data.get("name"),
            data.get("email"),
            data.get("department"),
            data.get("position"),
            data.get("salary"),
            id
        )
    )
    conn.commit()
    employee = cur.fetchone()  # Retrieve the updated employee record
    cur.close()
    conn.close()
    return employee  # Return the updated employee as JSON


@app.delete("/api/employees/{id}")
def delete_employee(id: int):
    # Delete an employee by ID
    conn = get_db_connection()
    cur = conn.cursor()  # Create a cursor (regular cursor, no dictionary needed for DELETE)
    cur.execute("DELETE FROM employees WHERE id = %s", (id,))  # Delete the employee with given ID
    conn.commit()
    deleted = cur.rowcount  # Get the number of rows deleted (1 if found, 0 if not)
    cur.close()
    conn.close()
    if deleted:
        return {"message": "Employee deleted"}  # Success message if a row was deleted
    return JSONResponse(content={"error": "Employee not found"}, status_code=404)


@app.get("/api/health")
def health():
    # Simple health check endpoint to verify the backend is running
    return {"status": "ok"}


# Initialize database on startup (runs when uvicorn imports this module)
init_db()


# Real-world analogy:
# Imagine you are a restaurant chef (the server) with one stove:
# - Synchronous (no await): You stand in front of the stove staring at a pot of water, waiting for it to boil. You cannot chop vegetables, greet customers, or do anything else while waiting. Everyone else waits.
# - Asynchronous (await): You put the pot on the stove, set a timer, and walk away to chop vegetables, help other customers, etc. When the timer rings (data arrives), you come back. Nobody waits.