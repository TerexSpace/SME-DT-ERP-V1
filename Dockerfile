# SME-DT-ERP: Digital Twin Framework for ERP-Integrated Warehouse Management
# Dockerfile for containerized deployment

# Use Python 3.11 slim image
FROM python:3.11-slim

# Set metadata
LABEL maintainer="[Author Name] <author@email.com>"
LABEL description="Digital Twin Framework for ERP-Integrated Warehouse Management in SMEs"
LABEL version="0.1.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Create directories for results
RUN mkdir -p /app/results /app/logs

# Default command - run simulation
CMD ["python", "-m", "sme_dt_erp.core"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from sme_dt_erp import SimulationConfig; print('OK')" || exit 1

# Expose port for future API
EXPOSE 8000
