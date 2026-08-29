# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core/ ./core/
COPY think_box_ai/ ./think_box_ai/

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Create non-root user
RUN groupadd -r thinkbox && useradd -r -g thinkbox thinkbox

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY core/ ./core/
COPY think_box_ai/ ./think_box_ai/

# Create data directory
RUN mkdir -p /data/thinkbox && chown -R thinkbox:thinkbox /data

USER thinkbox

ENV THINKBOX_DATA_DIR=/data/thinkbox
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "think_box_ai.api:app", "--host", "0.0.0.0", "--port", "8000"]
