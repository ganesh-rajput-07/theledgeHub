"""Public website: pricing, registration, and the customer's account area."""

import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import customers, money, services
from app.config import get_settings
from app.db import get_db
from app.models import Computer, CustomerSession, CustomerUser, Plan
from app.security import new_token, same, token_hash
from app.services import RuleError, now

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parents[1] / "templates"))
templates.env.filters["rupees"] = money.rupees
templates.env.filters["d"] = lambda value: value.strftime("%d %b %Y") if value else "-"
templates.env.filters["dt"] = lambda value: value.astimezone(money.IST).strftime("%d %b %Y, %H:%M") if value else "-"
templates.env.globals.update(METHODS=services.METHODS, ROLES=customers.ROLES)

COOKIE, FLASH = "kh_site", "kh_site_flash"


class CustomerLoginRequired(Exception):  # control flow: redirect to /login
    pass


class Me:
    def __init__(self, user: CustomerUser, session: CustomerSession, ip: str | None) -> None:
        self.user, self.session, self.ip = user, session, ip

    @property
    def firm(self):
        return self.user.firm


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def optional_me(request: Request, db: Session = Depends(get_db)) -> Me | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    session = db.scalar(select(CustomerSession).where(CustomerSession.token_hash == token_hash(token)))
    if session is None or session.expires_at < now() or not session.user.is_active:
        return None
    return Me(session.user, session, _ip(request))


def me_required(me: Me | None = Depends(optional_me)) -> Me:
    if me is None:
        raise CustomerLoginRequired
    return me


async def checked(request: Request, me: Me = Depends(me_required)) -> Me:
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Cross-site request refused")
    form = await request.form()
    if not same(form.get("csrf"), me.session.csrf_token):
        raise HTTPException(403, "Your form expired. Go back, reload the page and try again.")
    return me


def render(request: Request, name: str, me: Me | None, db: Session, status_code: int = 200, **values):
    flash = request.cookies.get(FLASH)
    config = services.settings(db)
    response = templates.TemplateResponse(
        request,
        name,
        {
            "me": me,
            "csrf": me.session.csrf_token if me else "",
            "flash": flash,
            "today": money.today(),
            "brand": config["business_name"],
            "support_email": config["support_email"],
            "support_phone": config["support_phone"],
            **values,
        },
        status_code=status_code,
    )
    if flash:
        response.delete_cookie(FLASH)
    return response


def go(url: str, message: str | None = None) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    if message:
        response.set_cookie(
            FLASH, message, max_age=30, httponly=True, samesite="lax", secure=get_settings().cookie_secure
        )
    return response


def _start_session(db: Session, user: CustomerUser, url: str, message: str | None = None) -> RedirectResponse:
    token = new_token()
    db.execute(delete(CustomerSession).where(CustomerSession.expires_at < now()))
    db.add(
        CustomerSession(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf_token=new_token(),
            expires_at=now() + timedelta(hours=get_settings().session_hours),
        )
    )
    db.commit()
    response = go(url, message)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        max_age=get_settings().session_hours * 3600,
    )
    return response


def _public_plans(db: Session) -> list[tuple[Plan, services.Quote]]:
    gst = services.gst_percent(db)
    return [
        (p, services.quote(p, p.computers_included, 1, gst))
        for p in services.plans(db, sellable_only=True)
        if p.is_public
    ]


# ------------------------------------------------------------------ public pages


@router.get("/", response_class=HTMLResponse)
def home(request: Request, me: Me | None = Depends(optional_me), db: Session = Depends(get_db)):
    return render(request, "site/home.html", me, db, plans=_public_plans(db), gst=services.gst_percent(db))


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request, plan: str = "", me: Me | None = Depends(optional_me), db: Session = Depends(get_db)
):
    if me:
        return go("/account")
    return render(request, "site/register.html", None, db, plans=_public_plans(db), form={"plan": plan})


@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db)):
    form = {k: str(v) for k, v in (await request.form()).items()}
    plans = _public_plans(db)
    if not customers.limiter.allow(f"register:{_ip(request)}", get_settings().register_ip_per_hour, 3600):
        return render(
            request,
            "site/register.html",
            None,
            db,
            429,
            plans=plans,
            form=form,
            error="Too many sign-ups from this network. Try again in an hour.",
        )
    try:
        if form.get("terms") != "on":
            raise RuleError("Please accept the terms to continue.")
        if form.get("password") != form.get("confirm_password"):
            raise RuleError("The two passwords don't match.")
        user = customers.register(db, form, form.get("password", ""), form.get("plan", ""), _ip(request))
    except RuleError as error:
        db.rollback()
        return render(request, "site/register.html", None, db, 400, plans=plans, form=form, error=str(error))
    return _start_session(db, user, "/account", "Welcome! Your account is created. Here's how to pay.")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, me: Me | None = Depends(optional_me), db: Session = Depends(get_db)):
    if me:
        return go("/account")
    return render(request, "site/login.html", None, db)


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = str(form.get("email", ""))
    user = customers.authenticate(db, email, str(form.get("password", "")), _ip(request), channel="website")
    if user is None:
        message = (
            "Too many wrong passwords. Try again in 15 minutes."
            if customers.is_locked(db, email)
            else "Wrong email or password."
        )
        return render(request, "site/login.html", None, db, 401, error=message, email=email)
    return _start_session(db, user, "/account")


@router.post("/logout")
def logout(request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    db.execute(delete(CustomerSession).where(CustomerSession.id == me.session.id))
    db.commit()
    response = go("/")
    response.delete_cookie(COOKIE)
    return response


# ------------------------------------------------------------------ account area


@router.get("/account", response_class=HTMLResponse)
def account(request: Request, me: Me = Depends(me_required), db: Session = Depends(get_db)):
    return render(request, "site/account.html", me, db, **_account_values(me, db))


def _account_values(me: Me, db: Session) -> dict:
    config = services.settings(db)
    firm = me.firm
    db.refresh(firm)
    status = services.firm_status(firm, int(config["grace_days"]))
    sub = firm.subscription
    plan = sub.plan if sub else (db.get(Plan, firm.requested_plan_id) if firm.requested_plan_id else None)
    computers_wanted = sub.computers_allowed if sub else None
    price = customers.price_for(db, plan, computers_wanted) if plan else None
    return {
        "nav": "account",
        "firm": firm,
        "status": status,
        "sub": sub,
        "plan": plan,
        "price": price,
        "config": config,
        "claims": customers.open_claims(db, firm),
        "computers": customers.computers(db, firm),
        "form": {},
    }


@router.post("/account/paid")
async def paid(request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    try:
        customers.claim_payment(
            db,
            me.user,
            amount=str(form.get("amount", "")),
            method=str(form.get("method", "")),
            utr=str(form.get("utr", "")),
            paid_on=str(form.get("paid_on", "")),
            note=str(form.get("note", "")),
            ip=me.ip,
        )
    except RuleError as error:
        db.rollback()
        values = _account_values(me, db) | {"error": str(error), "form": dict(form)}
        return render(request, "site/account.html", me, db, 400, **values)
    return go("/account", "Thank you! We'll confirm your payment and activate your account shortly.")


@router.get("/account/computers", response_class=HTMLResponse)
def computers_page(request: Request, me: Me = Depends(me_required), db: Session = Depends(get_db)):
    limit = int(services.settings(db)["computer_changes_per_month"])
    return render(
        request,
        "site/computers.html",
        me,
        db,
        nav="computers",
        computers=customers.computers(db, me.firm),
        sub=me.firm.subscription,
        removals_left=max(0, limit - customers.removals_this_month(db, me.firm)),
    )


@router.post("/account/computers/{computer_id}/remove")
async def computer_remove(computer_id: str, request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    try:
        computer = db.get(Computer, uuid.UUID(computer_id))
    except ValueError:
        computer = None
    if computer is None or computer.firm_id != me.firm.id:
        raise HTTPException(404, "Not found")
    try:
        customers.remove_own_computer(db, me.user, computer, me.ip)
    except RuleError as error:
        db.rollback()
        return go("/account/computers", str(error))
    return go("/account/computers", "Computer removed. You can now activate another one.")


@router.get("/account/team", response_class=HTMLResponse)
def team_page(request: Request, me: Me = Depends(me_required), db: Session = Depends(get_db)):
    return render(request, "site/team.html", me, db, nav="team", members=customers.team(db, me.firm), form={})


@router.post("/account/team")
async def team_add(request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    form = {k: str(v) for k, v in (await request.form()).items()}
    try:
        customers.add_member(
            db,
            me.user,
            me.firm,
            name=form.get("name", ""),
            email=form.get("email", ""),
            role=form.get("role", ""),
            password=form.get("password", ""),
            ip=me.ip,
        )
    except RuleError as error:
        db.rollback()
        return render(
            request,
            "site/team.html",
            me,
            db,
            400,
            nav="team",
            members=customers.team(db, me.firm),
            form=form,
            error=str(error),
        )
    return go("/account/team", f"Added {form.get('email')}. Share the password with them; they can change it.")


@router.post("/account/team/{user_id}")
async def team_toggle(user_id: str, request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    try:
        member = db.get(CustomerUser, uuid.UUID(user_id))
    except ValueError:
        member = None
    if member is None or member.firm_id != me.firm.id:
        raise HTTPException(404, "Not found")
    try:
        customers.set_member_active(db, me.user, member, form.get("active") == "1", me.ip)
    except RuleError as error:
        db.rollback()
        return go("/account/team", str(error))
    return go("/account/team", "Team updated.")


@router.get("/account/password", response_class=HTMLResponse)
def password_page(request: Request, me: Me = Depends(me_required), db: Session = Depends(get_db)):
    return render(request, "site/password.html", me, db, nav="password")


@router.post("/account/password")
async def password_save(request: Request, me: Me = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    try:
        customers.change_password(
            db,
            me.user,
            str(form.get("current_password", "")),
            str(form.get("new_password", "")),
            str(form.get("confirm_password", "")),
            me.ip,
        )
    except RuleError as error:
        db.rollback()
        return render(request, "site/password.html", me, db, 400, nav="password", error=str(error))
    return go("/account/password", "Password changed.")
