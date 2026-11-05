from fastapi import APIRouter

from app.core.config import get_settings
from app.licensing import lease as leases
from app.licensing import service as licensing

router = APIRouter(prefix="/licence", tags=["licence"])


@router.get("/status")
def status():
    """Open without a token, so the app can show 'licence ended' screens. Reveals nothing beyond the firm name."""
    if not licensing.desktop_mode():
        return {"mode": "off", "active": True}
    lease = leases.current()
    if lease is None:
        return {"mode": "desktop", "active": False, "app_version": get_settings().app_version}
    claims = lease.claims
    return {
        "mode": "desktop",
        "active": True,
        "seconds_left": lease.seconds_left,
        "firm": claims["firm"]["name"],
        "user": claims["user"]["email"],
        "plan": claims["plan"]["name"],
        "ends_on": claims["ends_on"],
        "trial": claims.get("trial", False),
        "app_version": get_settings().app_version,
    }
