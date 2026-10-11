FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system build dependencies for geospatial libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user (UID 1000 is required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH="/app/backend:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    URBIS_HOST=0.0.0.0 \
    URBIS_PORT=7860

# Pre-install Python dependencies as non-root user for build caching
COPY --chown=user:user backend/requirements.txt /app/backend/requirements.txt
USER user
RUN pip install --no-cache-dir --user --upgrade pip && \
    pip install --no-cache-dir --user -r /app/backend/requirements.txt

# Copy application source and precomputed processed data
USER root
COPY --chown=user:user . /app
RUN chown -R user:user /app

# Ensure non-root user has write permissions for caching/duckdb if needed
RUN mkdir -p /app/data/processed /app/backend/cache && \
    chown -R user:user /app/data /app/backend/cache

# Switch to non-root user
USER user

# Expose standard Hugging Face Spaces port
EXPOSE 7860

# Set working directory to backend module
WORKDIR /app/backend

# Launch FastAPI with uvicorn on port 7860
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
