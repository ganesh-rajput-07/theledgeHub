# KnowledgeHub AI - API image (CPU only)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/models \
    STORAGE_DIR=/data/storage

WORKDIR /app

# Runtime dependencies only (tests/linters live in requirements-dev.txt). CPU PyTorch via the index in the file.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install -r requirements.txt

# Bake the embedding model into the image so containers start offline and identically every time.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1

COPY alembic.ini .
COPY app ./app

RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /data/storage && chown -R appuser /data/storage
USER appuser

EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8001/health').status != 200)"

# One worker: login rate limits and ingestion background tasks are in-process (see README > Scaling).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]
