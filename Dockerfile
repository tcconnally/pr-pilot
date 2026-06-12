# Use Python 3.12 slim image
FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/
COPY pyproject.toml .

# Install the project itself so packaging metadata is the single source of
# truth for runtime imports (catches drift between requirements.txt and
# pyproject.toml at build time).
RUN pip install --no-cache-dir --no-deps .

# Create data dirs
RUN mkdir -p data/reviews logs/agents

# Run with uvicorn
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
