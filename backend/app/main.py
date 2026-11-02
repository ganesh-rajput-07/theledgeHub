import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.database.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the local models now, so the first question doesn't spend its time (and the browser's patience) on it.
    from app.rag.embeddings import get_embedding_provider

    get_embedding_provider()
    if settings.rerank_enabled:
        from app.rag.reranker import get_reranker

        get_reranker()
    logging.getLogger("knowledgehub").info("Models loaded")
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    description="AI-powered Research and Document Intelligence",
    version="0.1.0",
)
app.include_router(api_router)


@app.get("/")
def root():
    return {"message": f"{settings.app_name} API", "status": "running"}


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            pgvector = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
        database = "ok"
    except Exception:  # noqa: BLE001 - health must report, not raise
        pgvector, database = None, "unavailable"
    return {"status": "healthy", "database": database, "pgvector": pgvector}
