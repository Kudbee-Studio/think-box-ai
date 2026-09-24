# Think Box AI — API image (enterprise default)
FROM python:3.11-slim

LABEL org.opencontainers.image.title="think-box-ai" \
      org.opencontainers.image.description="Governed agent execution API" \
      org.opencontainers.image.source="https://github.com/Kudbee-Studio/think-box-ai"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN groupadd -r thinkbox && useradd -r -g thinkbox thinkbox

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY pyproject.toml LICENSE README.md ./
COPY core/ ./core/
COPY thinkbox/ ./thinkbox/
COPY think_box_ai/ ./think_box_ai/
COPY backend/ ./backend/
COPY public/ ./public/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e . --no-deps && \
    mkdir -p data/jobs data/findings data/raw data/fixtures data/logs && \
    chown -R thinkbox:thinkbox /app

USER thinkbox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
