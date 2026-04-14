FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management (optional, but good)
RUN pip install uv

# Copy requirements or pyproject.toml
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command can be overridden by docker-compose
CMD ["python", "-m", "app.runtime.runner"]
