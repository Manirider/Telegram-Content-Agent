# Build stage
FROM python:3.12-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser .env.example ./

# Create data directory for SQLite persistence
RUN mkdir -p /data && chown appuser:appuser /data

# Switch to non-root user
USER appuser

# Add user packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default port for health check (Render injects PORT)
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose health check port
EXPOSE 8080

# Run application
CMD ["python", "-m", "app.main"]