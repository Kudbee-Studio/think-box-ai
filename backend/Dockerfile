"""Dockerfile for kudbEE backend.

Builds a production image with PostgreSQL 19 + pgvector support via asyncpg.
For vector embeddings, sentence-transformers is optional (falls back to hash embeddings).

Build:  docker build -f backend/Dockerfile -t kudbee-backend .
Run:    docker run -e DATABASE_URL=postgresql://... -p 8000:8000 kudbee-backend
"""

FROM python:3.11-slim

WORKDIR /app

# System deps for building asyncpg / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY core/ /app/core/
COPY apps/ /app/apps/

ENV PYTHONPATH=/app
ENV MEMORY_BACKEND=postgres
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
