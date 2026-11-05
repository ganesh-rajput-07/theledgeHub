from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.admin.auth import LoginRequired
from app.admin.routes import router as admin_router

app = FastAPI(title="KnowledgeHub Licensing", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(admin_router)


@app.exception_handler(LoginRequired)
def to_login(request: Request, _exc: LoginRequired):
    return RedirectResponse("/login", status_code=303)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; "
        "form-action 'self'; base-uri 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
