import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.database.session import engine
from app.licensing import lease as leases
from app.licensing import service as licensing

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

# Reachable without a licence: sign-in, and the status the app needs to show "licence ended" screens.
LICENCE_FREE = {"/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/licence/status"}


@app.middleware("http")
async def require_licence(request: Request, call_next):
    """Installed app: every API call needs a valid lease. It is checked here, not only at sign-in, so a lease
    running out mid-session stops the app until the user signs in online again."""
    if (
        licensing.desktop_mode()
        and request.url.path.startswith("/api/")
        and request.url.path not in LICENCE_FREE
        and leases.current() is None
    ):
        return JSONResponse(
            {"detail": "Your licence session has ended. Sign in again (internet needed)."},
            status_code=402,
            headers={"X-Licence-Code": "licence_required"},
        )
    return await call_next(request)


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
