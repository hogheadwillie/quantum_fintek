# QuantumFintek API
# Multi-stage friendly; currently single stage for development clarity

FROM python:3.12-slim

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy monorepo packages first (better layer caching)
COPY packages/quant-core /app/packages/quant-core
COPY packages/ai-intel /app/packages/ai-intel

# Install local packages in editable mode
RUN pip install --no-cache-dir -e /app/packages/quant-core \
    && pip install --no-cache-dir -e /app/packages/ai-intel

# API requirements
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/api/requirements.txt

# Application code
COPY apps/api/app /app/apps/api/app

# Make the app package importable
ENV PYTHONPATH=/app/apps/api

EXPOSE 8000

# Development-friendly command (reload). Override in production.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
