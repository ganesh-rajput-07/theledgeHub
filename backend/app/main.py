from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.database.session import engine

settings = get_settings()

app = FastAPI(
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
