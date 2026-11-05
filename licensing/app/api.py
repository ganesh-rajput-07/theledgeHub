"""JSON API used by the desktop app."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import customers, lease, services
from app.config import get_settings
from app.db import get_db

router = APIRouter(prefix="/api/app/v1")


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=256)
    machine_id: str = Field(min_length=16, max_length=200)  # stable per installation; hashed before storage
    machine_name: str = Field(default="", max_length=120)
    app_version: str = Field(max_length=40)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status)


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    if not customers.limiter.allow(f"app-login:{ip}", get_settings().app_login_ip_per_15min, 900):
        return _error(429, "rate_limited", "Too many login attempts from this network. Try again in 15 minutes.")
    try:
        result = customers.app_login(
            db,
            email=body.email,
            password=body.password,
            machine_id=body.machine_id,
            machine_name=body.machine_name,
            app_version=body.app_version,
            ip=ip,
        )
    except customers.AppLoginError as error:
        return _error(error.status, error.code, error.message)
    except lease.LeaseKeyMissing:
        db.rollback()
        return _error(503, "server_not_ready", "The licence server isn't set up yet. Please try again later.")
    sub = result.firm.subscription
    config = services.settings(db)
    return {
        "lease": result.lease,
        "expires_at": result.expires_at.isoformat(),
        "valid_seconds": int((result.expires_at - services.now()).total_seconds()),
        "user": {"name": result.user.name, "email": result.user.email, "role": result.user.role},
        "firm": {"name": result.firm.name, "reference": result.firm.reference},
        "subscription": {
            "plan": sub.plan.name,
            "ends_on": sub.ends_on.isoformat(),
            "status": result.status.code,
            "days_left": result.status.days_left,
            "trial": sub.is_trial,
        },
        "latest_version": config["latest_version"] or None,
    }


@router.get("/public-key", response_class=PlainTextResponse)
def public_key():
    try:
        return lease.public_pem(lease.private_key().public_key())
    except lease.LeaseKeyMissing:
        return PlainTextResponse("not configured", status_code=503)
