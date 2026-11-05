import csv
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import customers, money, services
from app.admin.auth import COOKIE, Ctx, authenticate, checked, client_ip, current, end_session, start_session
from app.config import get_settings
from app.db import get_db
from app.models import AuditEvent, Computer, CustomerUser, Firm, Payment, PaymentClaim, Plan
from app.security import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.services import RuleError

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(__import__("pathlib").Path(__file__).parents[1] / "templates"))
templates.env.filters["rupees"] = money.rupees
templates.env.filters["d"] = lambda value: value.strftime("%d %b %Y") if value else "-"
templates.env.filters["dt"] = lambda value: value.astimezone(money.IST).strftime("%d %b %Y, %H:%M") if value else "-"
templates.env.globals["METHODS"] = services.METHODS
FLASH = "kh_admin_flash"


# ------------------------------------------------------------------ helpers


def render(request: Request, name: str, ctx: Ctx | None = None, status_code: int = 200, **values) -> HTMLResponse:
    flash = request.cookies.get(FLASH)
    response = templates.TemplateResponse(
        request,
        name,
        {
            "me": ctx.admin if ctx else None,
            "csrf": ctx.session.csrf_token if ctx else "",
            "flash": flash,
            "today": money.today(),
            **values,
        },
        status_code=status_code,
    )
    if flash:
        response.delete_cookie(FLASH, path="/admin")
    return response


def go(url: str, message: str | None = None) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    if message:
        response.set_cookie(
            FLASH,
            message,
            max_age=30,
            httponly=True,
            samesite="strict",
            secure=get_settings().cookie_secure,
            path="/admin",
        )
    return response


def _int(form, key: str, default: int | None = None, *, label: str) -> int | None:
    raw = (form.get(key) or "").strip()
    if not raw:
        if default is None:
            return None
        return default
    if not raw.lstrip("-").isdigit():
        raise RuleError(f"{label} must be a whole number.")
    return int(raw)


def _date(raw: str | None, label: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        raise RuleError(f"{label}: pick a valid date.") from None


def _get(db: Session, model, raw_id: str):
    try:
        obj = db.get(model, uuid.UUID(raw_id))
    except ValueError:
        obj = None
    if obj is None:
        raise HTTPException(404, "Not found")
    return obj


# ------------------------------------------------------------------ sign in


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "admin/login.html")


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ip = client_ip(request)
    admin = authenticate(db, str(form.get("email", "")), str(form.get("password", "")), ip)
    if admin is None:
        return render(
            request,
            "admin/login.html",
            status_code=401,
            error="Wrong email or password, or the account is locked for a few minutes after repeated attempts.",
            email=form.get("email", ""),
        )
    response = go("/admin/")
    response.set_cookie(
        COOKIE,
        start_session(db, admin, ip),
        httponly=True,
        samesite="strict",
        secure=get_settings().cookie_secure,
        max_age=get_settings().session_hours * 3600,
        path="/admin",
    )
    return response


@router.post("/logout")
def logout(request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    end_session(db, request.cookies.get(COOKIE))
    response = go("/admin/login")
    response.delete_cookie(COOKIE, path="/admin")
    return response


# ------------------------------------------------------------------ dashboard


@router.get("/", response_class=HTMLResponse)
def home(request: Request, ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    data = services.dashboard(db)
    data["claims"] = customers.open_claims(db)
    grace = int(services.settings(db)["grace_days"])
    return render(request, "admin/dashboard.html", ctx, nav="home", grace=grace, **data)


# ------------------------------------------------------------------ plans


def _plan_data(form) -> dict:
    def money_field(key: str, label: str) -> int:
        try:
            return money.parse_rupees(str(form.get(key) or "0"))
        except ValueError as error:
            raise RuleError(f"{label}: {error}") from None

    return {
        "name": str(form.get("name", "")).strip(),
        "code": str(form.get("code", "")).strip().lower(),
        "description": str(form.get("description", "")).strip(),
        "price_paise": money_field("price", "Price"),
        "billing_months": _int(form, "billing_months", 1, label="Billing period"),
        "computers_included": _int(form, "computers_included", 1, label="Computers included"),
        "extra_computer_paise": money_field("extra_computer_price", "Extra computer price"),
        "max_users": _int(form, "max_users", label="Max users"),
        "invoice_limit": _int(form, "invoice_limit", label="Invoices per month"),
        "is_active": form.get("is_active") == "on",
        "is_public": form.get("is_public") == "on",
        "sort_order": _int(form, "sort_order", 0, label="Order"),
    }


@router.get("/plans", response_class=HTMLResponse)
def plan_list(request: Request, ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    return render(
        request,
        "admin/plans.html",
        ctx,
        nav="plans",
        plans=services.plans(db),
        subscribers=services.subscriber_counts(db),
        gst=services.gst_percent(db),
    )


@router.get("/plans/new", response_class=HTMLResponse)
def plan_new(request: Request, ctx: Ctx = Depends(current)):
    return render(request, "admin/plan_form.html", ctx, nav="plans", plan=None, form={})


@router.get("/plans/{plan_id}", response_class=HTMLResponse)
def plan_edit(plan_id: str, request: Request, ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    plan = _get(db, Plan, plan_id)
    return render(
        request,
        "admin/plan_form.html",
        ctx,
        nav="plans",
        plan=plan,
        form={},
        subscribers=services.subscriber_counts(db).get(plan.id, 0),
    )


@router.post("/plans/new")
async def plan_create(request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    return await _plan_save(request, ctx, db, None)


@router.post("/plans/{plan_id}")
async def plan_update(plan_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    return await _plan_save(request, ctx, db, _get(db, Plan, plan_id))


async def _plan_save(request: Request, ctx: Ctx, db: Session, plan: Plan | None):
    form = await request.form()
    try:
        saved = services.save_plan(db, ctx.admin, plan, _plan_data(form), ctx.ip)
    except RuleError as error:
        db.rollback()
        return render(
            request,
            "admin/plan_form.html",
            ctx,
            status_code=400,
            nav="plans",
            plan=db.get(Plan, plan.id) if plan else None,
            form=dict(form),
            error=str(error),
        )
    return go("/admin/plans", f"Saved plan {saved.name}.")


# ------------------------------------------------------------------ firms

FIRM_FIELDS = ("name", "contact_name", "email", "mobile", "city", "gstin", "notes")


@router.get("/firms", response_class=HTMLResponse)
def firm_list(
    request: Request, status: str = "", q: str = "", ctx: Ctx = Depends(current), db: Session = Depends(get_db)
):
    grace = int(services.settings(db)["grace_days"])
    query = select(Firm).order_by(Firm.created_at.desc())
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Firm.name.ilike(like),
                Firm.email.ilike(like),
                Firm.reference.ilike(like),
                Firm.mobile.ilike(like),
                Firm.city.ilike(like),
            )
        )
    rows = [(firm, services.firm_status(firm, grace)) for firm in db.scalars(query).unique()]
    if status:
        rows = [row for row in rows if row[1].code == status]
    return render(request, "admin/firms.html", ctx, nav="firms", rows=rows, status=status, q=q)


@router.get("/firms/new", response_class=HTMLResponse)
def firm_new(request: Request, ctx: Ctx = Depends(current)):
    return render(request, "admin/firm_new.html", ctx, nav="firms", form={})


@router.post("/firms/new")
async def firm_create(request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    try:
        firm = services.create_firm(db, ctx.admin, {k: str(form.get(k, "")) for k in FIRM_FIELDS}, ctx.ip)
    except RuleError as error:
        db.rollback()
        return render(
            request, "admin/firm_new.html", ctx, status_code=400, nav="firms", form=dict(form), error=str(error)
        )
    return go(f"/admin/firms/{firm.id}", f"Created {firm.name}. Payment reference: {firm.reference}")


def _firm_page(request: Request, ctx: Ctx, db: Session, firm: Firm, status_code: int = 200, **extra):
    db.refresh(firm)
    config = services.settings(db)
    sellable = services.plans(db, sellable_only=True)
    payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.firm_id == firm.id)
            .order_by(Payment.paid_on.desc(), Payment.created_at.desc())
        ).unique()
    )
    computers = list(db.scalars(select(Computer).where(Computer.firm_id == firm.id).order_by(Computer.first_seen)))
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.firm_id == firm.id).order_by(AuditEvent.created_at.desc()).limit(30)
        ).unique()
    )
    plan_js = {
        str(p.id): {
            "price": p.price_paise,
            "months": p.billing_months,
            "included": p.computers_included,
            "extra": p.extra_computer_paise,
        }
        for p in sellable
    }
    return render(
        request,
        "admin/firm.html",
        ctx,
        status_code=status_code,
        nav="firms",
        firm=firm,
        status=services.firm_status(firm, int(config["grace_days"])),
        plans=sellable,
        plan_js=plan_js,
        payments=payments,
        computers=computers,
        events=events,
        config=config,
        users=customers.team(db, firm),
        claims=customers.open_claims(db, firm),
        requested=db.get(Plan, firm.requested_plan_id) if firm.requested_plan_id else None,
        form=extra.pop("form", {}),
        **extra,
    )


@router.get("/firms/{firm_id}", response_class=HTMLResponse)
def firm_detail(
    firm_id: str, request: Request, claim: str = "", ctx: Ctx = Depends(current), db: Session = Depends(get_db)
):
    firm = _get(db, Firm, firm_id)
    if claim:
        found = _get(db, PaymentClaim, claim)
        if found.firm_id != firm.id:
            raise HTTPException(404, "Not found")
        form = {
            "amount": f"{found.amount_paise / 100:.2f}",
            "method": found.method,
            "utr": found.utr,
            "paid_on": found.paid_on.isoformat(),
            "claim_id": str(found.id),
        }
        if found.plan_id:
            form["plan_id"] = str(found.plan_id)
        return _firm_page(request, ctx, db, firm, panel="payment", form=form)
    return _firm_page(request, ctx, db, firm)


async def _firm_action(request: Request, ctx: Ctx, db: Session, firm_id: str, panel: str, action) -> Response:
    firm = _get(db, Firm, firm_id)
    form = await request.form()
    try:
        message = action(firm, form)
    except RuleError as error:
        db.rollback()
        return _firm_page(request, ctx, db, firm, status_code=400, error=str(error), panel=panel, form=dict(form))
    return go(f"/admin/firms/{firm.id}", message)


@router.post("/firms/{firm_id}/edit")
async def firm_edit(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        services.update_firm(db, ctx.admin, firm, {k: str(form.get(k, "")) for k in FIRM_FIELDS}, ctx.ip)
        return "Firm details saved."

    return await _firm_action(request, ctx, db, firm_id, "edit", act)


@router.post("/firms/{firm_id}/payment")
async def firm_payment(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        plan = db.get(Plan, uuid.UUID(str(form.get("plan_id")))) if form.get("plan_id") else None
        if plan is None:
            raise RuleError("Choose a plan.")
        try:
            amount = money.parse_rupees(str(form.get("amount", "")))
        except ValueError as error:
            raise RuleError(f"Amount: {error}") from None
        payment = services.record_payment(
            db,
            ctx.admin,
            firm,
            plan=plan,
            computers=_int(form, "computers", plan.computers_included, label="Computers"),
            periods=_int(form, "periods", 1, label="Periods"),
            amount_paise=amount,
            method=str(form.get("method", "")),
            utr=str(form.get("utr", "")),
            paid_on=_date(form.get("paid_on"), "Payment date"),
            note=str(form.get("note", "")),
            ip=ctx.ip,
        )
        claim_id = str(form.get("claim_id") or "")
        if claim_id:
            claim = db.get(PaymentClaim, uuid.UUID(claim_id))
            if claim and claim.firm_id == firm.id and claim.status == "open":
                claim.status = "confirmed"
                db.commit()
        return f"Payment recorded. {firm.name} has access until {payment.covers_to:%d %b %Y}."

    return await _firm_action(request, ctx, db, firm_id, "payment", act)


@router.post("/firms/{firm_id}/claims/{claim_id}/dismiss")
async def claim_dismiss(
    firm_id: str, claim_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)
):
    def act(firm, form):
        claim = _get(db, PaymentClaim, claim_id)
        if claim.firm_id != firm.id or claim.status != "open":
            raise HTTPException(404, "Not found")
        claim.status = "dismissed"
        services.audit(
            db,
            ctx.admin,
            "payment.claim_dismiss",
            f"Dismissed reported payment {money.rupees(claim.amount_paise)} (UTR {claim.utr}) "
            f"from {firm.name}: {str(form.get('reason', '')).strip() or 'no reason given'}",
            firm=firm,
            ip=ctx.ip,
        )
        db.commit()
        return "Reported payment dismissed."

    return await _firm_action(request, ctx, db, firm_id, "payment", act)


@router.post("/firms/{firm_id}/users")
async def firm_add_user(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        customers.add_member(
            db,
            None,
            firm,
            name=str(form.get("name", "")),
            email=str(form.get("email", "")),
            role=str(form.get("role", "")),
            password=str(form.get("password", "")),
            ip=ctx.ip,
            admin=ctx.admin,
        )
        return f"Login created for {form.get('email')}. Share the password with them."

    return await _firm_action(request, ctx, db, firm_id, "users", act)


@router.post("/firms/{firm_id}/users/{user_id}/password")
async def firm_user_password(
    firm_id: str, user_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)
):
    def act(firm, form):
        user = _get(db, CustomerUser, user_id)
        if user.firm_id != firm.id:
            raise HTTPException(404, "Not found")
        password = str(form.get("password", ""))
        if len(password) < MIN_PASSWORD_LENGTH:
            raise RuleError(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")
        user.password_hash, user.failed_logins, user.locked_until = hash_password(password), 0, None
        services.audit(
            db, ctx.admin, "customer.password_reset", f"Reset the password of {user.email}", firm=firm, ip=ctx.ip
        )
        db.commit()
        return f"New password set for {user.email}. Share it with them; they can change it in their account."

    return await _firm_action(request, ctx, db, firm_id, "users", act)


@router.post("/firms/{firm_id}/trial")
async def firm_trial(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        plan = db.get(Plan, uuid.UUID(str(form.get("plan_id")))) if form.get("plan_id") else None
        if plan is None:
            raise RuleError("Choose a plan for the trial.")
        services.grant_trial(
            db,
            ctx.admin,
            firm,
            plan=plan,
            days=_int(form, "days", 14, label="Days"),
            computers=_int(form, "computers", 1, label="Computers"),
            ip=ctx.ip,
        )
        return f"Trial started for {firm.name}."

    return await _firm_action(request, ctx, db, firm_id, "trial", act)


@router.post("/firms/{firm_id}/adjust")
async def firm_adjust(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        services.adjust_subscription(
            db,
            ctx.admin,
            firm,
            ends_on=_date(form.get("ends_on"), "End date"),
            computers=_int(form, "computers", 1, label="Computers"),
            reason=str(form.get("reason", "")),
            ip=ctx.ip,
        )
        return "Subscription adjusted."

    return await _firm_action(request, ctx, db, firm_id, "adjust", act)


@router.post("/firms/{firm_id}/block")
async def firm_block(firm_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    def act(firm, form):
        blocking = form.get("blocked") == "1"
        services.set_blocked(db, ctx.admin, firm, blocking, str(form.get("reason", "")), ctx.ip)
        return f"{firm.name} {'blocked' if blocking else 'unblocked'}."

    return await _firm_action(request, ctx, db, firm_id, "block", act)


@router.post("/firms/{firm_id}/computers/{computer_id}")
async def computer_action(
    firm_id: str, computer_id: str, request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)
):
    def act(firm, form):
        computer = _get(db, Computer, computer_id)
        if computer.firm_id != firm.id:
            raise HTTPException(404, "Not found")
        op = form.get("op")
        if op == "remove":
            services.remove_computer(db, ctx.admin, computer, firm, ctx.ip)
            return "Computer removed; the seat is free again."
        if op in ("block", "unblock"):
            services.set_computer_blocked(db, ctx.admin, computer, firm, op == "block", ctx.ip)
            return f"Computer {op}ed."
        raise RuleError("Unknown action.")

    return await _firm_action(request, ctx, db, firm_id, "computers", act)


# ------------------------------------------------------------------ payments


def _month(raw: str) -> date:
    try:
        return date.fromisoformat(f"{raw}-01") if raw else money.today().replace(day=1)
    except ValueError:
        return money.today().replace(day=1)


def _payments_in(db: Session, start: date) -> list[Payment]:
    end = money.add_months(start, 1)
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.paid_on >= start, Payment.paid_on < end)
            .order_by(Payment.paid_on.desc(), Payment.created_at.desc())
        ).unique()
    )


@router.get("/payments", response_class=HTMLResponse)
def payment_list(request: Request, month: str = "", ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    start = _month(month)
    rows = _payments_in(db, start)
    return render(
        request,
        "admin/payments.html",
        ctx,
        nav="payments",
        rows=rows,
        month=start,
        prev=money.add_months(start, -1),
        next=money.add_months(start, 1),
        total=sum(p.amount_paise for p in rows),
        gst_total=sum(p.gst_paise for p in rows),
    )


def _cell(value) -> str:
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text  # no formula injection in Excel


@router.get("/payments.csv")
def payment_csv(month: str = "", ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    start = _month(month)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Paid on",
            "Firm",
            "Reference",
            "Firm GSTIN",
            "Plan",
            "Amount (incl. GST)",
            "GST",
            "Method",
            "UTR",
            "Covers from",
            "Covers to",
            "Note",
        ]
    )
    for p in _payments_in(db, start):
        writer.writerow(
            [
                _cell(v)
                for v in (
                    p.paid_on,
                    p.firm.name,
                    p.firm.reference,
                    p.firm.gstin,
                    p.plan.name,
                    f"{p.amount_paise / 100:.2f}",
                    f"{p.gst_paise / 100:.2f}",
                    services.METHODS.get(p.method, p.method),
                    p.utr,
                    p.covers_from,
                    p.covers_to,
                    p.note,
                )
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="payments-{start:%Y-%m}.csv"'},
    )


# ------------------------------------------------------------------ settings, activity, account


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    return render(request, "admin/settings.html", ctx, nav="settings", values=services.settings(db))


@router.post("/settings")
async def settings_save(request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    try:
        services.save_settings(db, ctx.admin, {k: str(v) for k, v in form.items()}, ctx.ip)
    except RuleError as error:
        db.rollback()
        return render(
            request,
            "admin/settings.html",
            ctx,
            status_code=400,
            nav="settings",
            values=services.settings(db) | {k: str(v) for k, v in form.items()},
            error=str(error),
        )
    return go("/admin/settings", "Settings saved.")


@router.get("/activity", response_class=HTMLResponse)
def activity(request: Request, page: int = 1, ctx: Ctx = Depends(current), db: Session = Depends(get_db)):
    page = max(1, page)
    size = 50
    total = db.scalar(select(func.count()).select_from(AuditEvent)) or 0
    events = list(
        db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).offset((page - 1) * size).limit(size)
        ).unique()
    )
    return render(
        request, "admin/activity.html", ctx, nav="activity", events=events, page=page, more=page * size < total
    )


@router.get("/account", response_class=HTMLResponse)
def account(request: Request, ctx: Ctx = Depends(current)):
    return render(request, "admin/account.html", ctx, nav="account")


@router.post("/account")
async def account_save(request: Request, ctx: Ctx = Depends(checked), db: Session = Depends(get_db)):
    form = await request.form()
    new = str(form.get("new_password", ""))
    error = None
    if not verify_password(str(form.get("current_password", "")), ctx.admin.password_hash):
        error = "Current password is wrong."
    elif len(new) < MIN_PASSWORD_LENGTH:
        error = f"New password must be at least {MIN_PASSWORD_LENGTH} characters."
    elif new != form.get("confirm_password"):
        error = "The two new passwords don't match."
    if error:
        return render(request, "admin/account.html", ctx, status_code=400, nav="account", error=error)
    admin = db.merge(ctx.admin)
    admin.password_hash = hash_password(new)
    services.audit(db, admin, "admin.password", f"{admin.email} changed their password", ip=ctx.ip)
    db.commit()
    return go("/admin/account", "Password changed.")
