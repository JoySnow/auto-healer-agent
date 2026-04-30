FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# Copy application code
COPY app.py .

# Expose port
EXPOSE 8003

# Run the service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8003"]
