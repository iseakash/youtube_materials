# Use official Python image as the base image
FROM python:3.12-slim

# Set working directory in the container
WORKDIR /app

# Copy requirements.txt to the container
COPY requirements.txt .

# Install dependencies without using cache to reduce image size
# The --no-cache-dir option tells pip not to store the downloaded packages in a cache directory, which can help reduce the size of the Docker image.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the container
COPY main.py .

# Expose the port that the FastAPI app will run on
EXPOSE 8000

# Start the FastAPI app using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]