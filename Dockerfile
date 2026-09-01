FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r thinkbox && useradd -r -g thinkbox thinkbox

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY backend/ ./backend/
COPY think_box_ai/ ./think_box_ai/
COPY pyproject.toml .
COPY scripts/ ./scripts/

RUN pip install -e .

RUN mkdir -p data/jobs data/findings data/raw data/fixtures data/logs && \
    chown -R thinkbox:thinkbox /app

USER thinkbox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
