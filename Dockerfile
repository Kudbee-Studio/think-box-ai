FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p data/findings data/raw data/fixtures jobs/queue jobs/active jobs/done jobs/blocked

# Initialize database
RUN python -c "from core.database import init_db, seed_db; conn = init_db(); seed_db(conn); conn.close()"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
