FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Setup environment
ENV PYTHONPATH=/app
ENV MODULE_NAME="app.main"

# Command to run
CMD ["python", "-m", "app.main"]