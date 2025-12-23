# UIA-App v1.0.0
# Multi-stage build for Palo Alto UIA Testing Tool

# Stage 1: Build Frontend
FROM node:20-slim AS build-stage
WORKDIR /app/gui
COPY gui/package*.json ./
RUN npm ci --silent
COPY gui/ ./
RUN npm run build

# Stage 2: Runtime
FROM python:3.11-slim

# Metadata
LABEL org.opencontainers.image.title="UIA-App"
LABEL org.opencontainers.image.description="Testing tool for Palo Alto Networks User-ID Agent"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="UIA-App Team"

WORKDIR /app

# Install system dependencies for cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY main.py .
COPY generate_certs.py .
COPY VERSION .

# Copy built frontend from Stage 1
COPY --from=build-stage /app/gui/dist ./gui/dist

# Create certs directory (will be mounted as volume)
RUN mkdir -p /app/certs

# Set environment
ENV CERT_DIR=/app/certs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
