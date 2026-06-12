from flask import Flask, render_template, request, jsonify          # Flask framework for web server, rendering HTML templates, handling requests, and returning JSON responses
import mysql.connector              # MySQL connector to interact with the MySQL database
import os                           # to read environment variables (DB_HOST, DB_USER, etc.)
import time                         # to add delays when waiting for the database to be ready

# Create the Flask application instance
app = Flask(__name__)


# Function to establish a connection to the MySQL database
def get_db():
    # Connect using environment variables (set in docker-compose.yml) with fallback defaults
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "db"),                       # Service name in docker-compose
        user=os.environ.get("DB_USER", "root"),                     # MySQL root user
        password=os.environ.get("DB_PASSWORD", "rootpassword"),     # Root password
        database=os.environ.get("DB_NAME", "sales_db"),             # Database name
    )


# Function to initialize the database - runs on container startup
def init_db():
    # Retry up to 15 times (with 2-second gaps) to handle MySQL not being ready yet
    for i in range(15):
        try:
            # Try connecting to MySQL
            db = get_db()
            cursor = db.cursor()

            # Create the sales table if it does not already exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sales (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sale_date DATE NOT NULL,
                    product VARCHAR(100) NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL
                )
            ''')

            # Commit the table creation to the database
            db.commit()
            # Close cursor and connection
            cursor.close()
            db.close()
            
            # Log success - this appears in `docker compose logs app`
            print("Database initialized successfully")
            return  # Exit the function once initialization succeeds
        except Exception as e:
            # If MySQL is not ready yet, wait 2 seconds and retry
            print(f"Waiting for database... attempt {i + 1}: {e}")
            time.sleep(2)
    # If all 15 attempts fail, log the failure
    print("Failed to connect to database")


# Route: Home page - serves the HTML frontend
@app.route("/")
def home():
    # Render the index.html template from the templates/ folder
    return render_template("index.html")


# Route: GET /api/sales - returns all sales records as JSON
@app.route("/api/sales", methods=["GET"])
def get_sales():
    # Connect to the database
    db = get_db()

    # Create a cursor that returns rows as dictionaries (column name to value)
    cursor = db.cursor(dictionary=True)

    # Fetch all sales, ordered by date (most recent first)
    cursor.execute("SELECT * FROM sales ORDER BY sale_date DESC")
    sales = cursor.fetchall()

    # Close cursor and connection
    cursor.close()
    db.close()

    # Convert date objects to strings (they are not JSON-serializable by default)
    for s in sales:
        s["sale_date"] = str(s["sale_date"])

    # Return the sales list as a JSON response
    return jsonify(sales)


# Route: POST /api/sales - adds a new sale record
@app.route("/api/sales", methods=["POST"])
def add_sale():
    # Parse the JSON body sent by the frontend
    data = request.get_json()
    # Connect to the database
    db = get_db()
    cursor = db.cursor()
    # Insert the new sale into the sales table
    cursor.execute(
        "INSERT INTO sales (sale_date, product, amount) VALUES (%s, %s, %s)",
        (data["sale_date"], data["product"], data["amount"]),
    )
    # Commit the transaction to save the data permanently
    db.commit()
    # Close cursor and connection
    cursor.close()
    db.close()
    # Return a success message with HTTP 201 (Created)
    return jsonify({"message": "Sale added"}), 201


# Route: DELETE /api/sales - deletes all sales records (used for demo reset)
@app.route("/api/sales", methods=["DELETE"])
def delete_sales():
    # Connect to the database
    db = get_db()
    cursor = db.cursor()
    # Delete every row from the sales table
    cursor.execute("DELETE FROM sales")
    # Commit the deletion
    db.commit()
    # Close cursor and connection
    cursor.close()
    db.close()
    # Return a success message
    return jsonify({"message": "All sales deleted"})


# Entry point - runs only when this file is executed directly (python app.py)
if __name__ == "__main__":
    init_db()  # Ensure the sales table exists before accepting requests
    # Start the Flask development server on port 5000, accessible from any IP
    app.run(host="0.0.0.0", port=5000, debug=True)
