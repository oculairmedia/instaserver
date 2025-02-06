FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user and switch to it
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 54068

# Command to run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:54068", "--timeout", "120", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:app"]