from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import money
from app.models import AuditEvent, Computer, Firm, Payment, Plan

TODAY = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(money, "today", lambda: TODAY)


def make_plan(browser, **overrides):
    data = {
        "name": "Team",
        "code": "team",
        "price": "2,499",
        "billing_months": "1",
        "computers_included": "3",
        "extra_computer_price": "699",
        "is_active": "on",
        "is_public": "on",
    } | overrides
    response = browser.post("/admin/plans/new", data)
    assert response.status_code == 303, response.text
    return data


def make_firm(browser, email="shah@example.com", **overrides):
    data = {"name": "Shah & Associates", "email": email, "mobile": "98250 12345", "city": "Surat"} | overrides
    response = browser.post("/admin/firms/new", data)
    assert response.status_code == 303, response.text
    return response.headers["location"]


def plan_id(db, code="team"):
    return str(db.scalar(select(Plan.id).where(Plan.code == code)))


def pay(browser, firm_url, db, **overrides):
    data = {
        "plan_id": plan_id(db),
        "computers": "3",
        "periods": "1",
        "amount": "2948.82",
        "method": "upi",
        "utr": "UTR123",
        "paid_on": TODAY.isoformat(),
    } | overrides
    return browser.post(f"{firm_url}/payment", data)


def subscription(db, firm_url):
    db.expire_all()
    firm = db.get(Firm, __import__("uuid").UUID(firm_url.rsplit("/", 1)[1]))
    return firm.subscription


# ------------------------------------------------------------------ access control


def test_pages_require_sign_in(client):
    for url in (
        "/admin/",
        "/admin/firms",
        "/admin/plans",
        "/admin/payments",
        "/admin/settings",
        "/admin/activity",
        "/admin/payments.csv",
    ):
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/admin/login", url


def test_wrong_password_and_lockout(client, admin, db):
    for _ in range(5):
        assert client.post("/admin/login", data={"email": admin.email, "password": "wrong-password"}).status_code == 401
    # Locked now: even the right password is refused for a while.
    response = client.post("/admin/login", data={"email": admin.email, "password": "admin-password-123"})
    assert response.status_code == 401
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "admin.locked"))


def test_posts_need_csrf_token_and_same_origin(browser):
    response = browser.client.post("/admin/plans/new", data={"name": "X"}, follow_redirects=False)
    assert response.status_code == 403
    response = browser.post("/admin/plans/new", {"name": "X"}, headers={"origin": "https://evil.example"})
    assert response.status_code == 403


def test_sign_out_ends_the_session(browser):
    assert browser.post("/admin/logout").status_code == 303
    assert browser.get("/admin/", follow_redirects=False).status_code == 303


def test_security_headers(browser):
    headers = browser.get("/admin/").headers
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["cache-control"] == "no-store"


# ------------------------------------------------------------------ plans


def test_create_and_edit_plan_price_is_audited(browser, db):
    make_plan(browser)
    assert "₹2,499" in browser.get("/admin/plans").text
    response = browser.post(
        f"/admin/plans/{plan_id(db)}",
        {
            "name": "Team",
            "code": "team",
            "price": "2,999",
            "billing_months": "1",
            "computers_included": "3",
            "extra_computer_price": "699",
            "is_active": "on",
        },
    )
    assert response.status_code == 303
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "plan.update"))
    assert "₹2,499 → ₹2,999" in event.summary
    plan = db.scalar(select(Plan).where(Plan.code == "team"))
    assert plan.price_paise == 299900 and plan.is_public is False  # unticked box = off


def test_plan_validation(browser):
    make_plan(browser)
    assert browser.post("/admin/plans/new", {"name": "Dup", "code": "team", "price": "1"}).status_code == 400
    assert browser.post("/admin/plans/new", {"name": "Bad", "code": "Bad Code", "price": "1"}).status_code == 400
    assert browser.post("/admin/plans/new", {"name": "Neg", "code": "neg", "price": "-5"}).status_code == 400
    assert (
        browser.post("/admin/plans/new", {"name": "Q", "code": "q", "price": "1", "billing_months": "2"}).status_code
        == 400
    )


def test_price_change_does_not_touch_existing_subscriptions(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    assert pay(browser, firm_url, db).status_code == 303
    browser.post(
        f"/admin/plans/{plan_id(db)}",
        {
            "name": "Team",
            "code": "team",
            "price": "3,999",
            "billing_months": "1",
            "computers_included": "3",
            "is_active": "on",
        },
    )
    assert subscription(db, firm_url).price_paise == 249900


# ------------------------------------------------------------------ firms


def test_firm_validation(browser):
    make_firm(browser)
    assert browser.post("/admin/firms/new", {"name": "Other", "email": "SHAH@example.com"}).status_code == 400
    assert browser.post("/admin/firms/new", {"name": "X", "email": "not-an-email"}).status_code == 400
    assert browser.post("/admin/firms/new", {"name": "X", "email": "x@example.com", "gstin": "123"}).status_code == 400
    assert (
        browser.post("/admin/firms/new", {"name": "X", "email": "x@example.com", "mobile": "12345"}).status_code == 400
    )


def test_new_firm_is_pending_with_reference(browser, db):
    firm_url = make_firm(browser)
    firm = db.scalar(select(Firm))
    assert firm.reference.startswith("KH-")
    page = browser.get(firm_url).text
    assert "Pending payment" in page and firm.reference in page
    assert "Shah &amp; Associates" in browser.get("/admin/firms?status=pending").text
    assert "Shah" not in browser.get("/admin/firms?status=active").text


# ------------------------------------------------------------------ payments & subscriptions


def test_first_payment_activates_for_one_month(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    assert pay(browser, firm_url, db).status_code == 303
    sub = subscription(db, firm_url)
    assert (sub.ends_on, sub.computers_allowed, sub.price_paise, sub.is_trial) == (date(2026, 12, 4), 3, 249900, False)
    payment = db.scalar(select(Payment))
    assert payment.gst_paise == 44982  # 2948.82 incl. 18% GST
    assert "Active" in browser.get(firm_url).text


def test_early_renewal_continues_from_end_date(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db)
    pay(browser, firm_url, db, periods="2", amount="5897.64")
    assert subscription(db, firm_url).ends_on == date(2027, 2, 4)


def test_renewal_after_expiry_starts_today(browser, db, monkeypatch):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db)
    later = date(2027, 1, 10)
    monkeypatch.setattr(money, "today", lambda: later)
    pay(browser, firm_url, db, paid_on=later.isoformat())
    assert subscription(db, firm_url).ends_on == date(2027, 2, 9)


def test_extra_computers_priced_into_the_subscription(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db, computers="5", amount="4598.46")
    sub = subscription(db, firm_url)
    assert (sub.computers_allowed, sub.price_paise) == (5, 249900 + 2 * 69900)
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "payment.record"))
    assert "price list" not in event.summary  # amount matched the price list


def test_payment_rules(browser, db):
    make_plan(browser)
    make_plan(browser, name="Old", code="old", is_active="")
    firm_url = make_firm(browser)
    assert pay(browser, firm_url, db, plan_id=plan_id(db, "old")).status_code == 400  # not on sale
    assert pay(browser, firm_url, db, paid_on=(TODAY + timedelta(days=1)).isoformat()).status_code == 400
    assert pay(browser, firm_url, db, computers="1").status_code == 400  # below the plan's included 3
    assert pay(browser, firm_url, db, amount="0").status_code == 400
    assert pay(browser, firm_url, db, method="bitcoin").status_code == 400
    assert subscription(db, firm_url) is None


def test_payment_below_price_list_is_flagged_in_log(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db, amount="2000")
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "payment.record"))
    assert "price list total is ₹2,948.82" in event.summary


def test_trial_then_payment_starts_today(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    assert (
        browser.post(f"{firm_url}/trial", {"plan_id": plan_id(db), "days": "14", "computers": "1"}).status_code == 303
    )
    sub = subscription(db, firm_url)
    assert (sub.is_trial, sub.ends_on, sub.price_paise) == (True, date(2026, 11, 18), 0)
    pay(browser, firm_url, db)
    sub = subscription(db, firm_url)
    assert (sub.is_trial, sub.ends_on) == (False, date(2026, 12, 4))
    # A paying firm can't be put back on a trial.
    assert browser.post(f"{firm_url}/trial", {"plan_id": plan_id(db), "days": "14"}).status_code == 400


def test_adjust_needs_reason_and_is_logged(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db)
    assert browser.post(f"{firm_url}/adjust", {"ends_on": "2026-12-10", "computers": "3"}).status_code == 400
    response = browser.post(
        f"{firm_url}/adjust", {"ends_on": "2026-12-10", "computers": "4", "reason": "install delay"}
    )
    assert response.status_code == 303
    assert (subscription(db, firm_url).ends_on, subscription(db, firm_url).computers_allowed) == (date(2026, 12, 10), 4)
    assert "install delay" in db.scalar(select(AuditEvent).where(AuditEvent.action == "subscription.adjust")).summary


def test_block_and_unblock(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    pay(browser, firm_url, db)
    assert browser.post(f"{firm_url}/block", {"blocked": "1"}).status_code == 400  # reason required
    assert browser.post(f"{firm_url}/block", {"blocked": "1", "reason": "shared licence"}).status_code == 303
    assert "Blocked: shared licence" in browser.get(firm_url).text
    assert browser.post(f"{firm_url}/block", {"blocked": "0"}).status_code == 303
    assert "Active" in browser.get(firm_url).text


def test_computers_can_be_blocked_and_removed_only_within_their_firm(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser)
    other_url = make_firm(browser, email="other@example.com", name="Other")
    firm = db.scalar(select(Firm).where(Firm.email == "shah@example.com"))
    computer = Computer(firm_id=firm.id, machine_hash="a" * 64, name="Reception PC")
    db.add(computer)
    db.commit()
    assert browser.post(f"{other_url}/computers/{computer.id}", {"op": "remove"}).status_code == 404
    assert browser.post(f"{firm_url}/computers/{computer.id}", {"op": "block"}).status_code == 303
    db.refresh(computer)
    assert computer.blocked
    computer_id = computer.id
    assert browser.post(f"{firm_url}/computers/{computer_id}", {"op": "remove"}).status_code == 303
    db.expire_all()
    assert db.get(Computer, computer_id) is None


# ------------------------------------------------------------------ payments page, settings, account


def test_payments_csv_escapes_formulas(browser, db):
    make_plan(browser)
    firm_url = make_firm(browser, name='=HYPERLINK("http://x")')
    pay(browser, firm_url, db, note="+cmd")
    csv_text = browser.get("/admin/payments.csv?month=2026-11").text
    assert "'=HYPERLINK" in csv_text and "'+cmd" in csv_text
    assert "2948.82" in csv_text


def test_dashboard_numbers(browser, db):
    make_plan(browser)
    pay(browser, make_firm(browser), db)
    make_firm(browser, email="pending@example.com", name="Pending Firm")
    page = browser.get("/admin/").text
    assert "₹2,499" in page  # monthly recurring revenue, excl. GST
    assert "₹2,948.82" in page  # collected this month
    assert "Pending Firm" in page


def test_settings_validation_and_save(browser, db):
    assert browser.post("/admin/settings", {"grace_days": "40"}).status_code == 400
    assert browser.post("/admin/settings", {"gst_percent": "abc"}).status_code == 400
    assert browser.post("/admin/settings", {"business_gstin": "XYZ"}).status_code == 400
    assert browser.post("/admin/settings", {"upi_id": "ganesh@okhdfcbank", "grace_days": "3"}).status_code == 303
    assert "ganesh@okhdfcbank" in browser.get("/admin/settings").text
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "settings.update"))
    assert event.details["grace_days"] == {"from": "0", "to": "3"}


def test_change_password(browser, client):
    assert (
        browser.post(
            "/admin/account", {"current_password": "nope", "new_password": "x" * 12, "confirm_password": "x" * 12}
        ).status_code
        == 400
    )
    assert (
        browser.post(
            "/admin/account",
            {"current_password": "admin-password-123", "new_password": "short", "confirm_password": "short"},
        ).status_code
        == 400
    )
    assert (
        browser.post(
            "/admin/account",
            {
                "current_password": "admin-password-123",
                "new_password": "new-password-456",
                "confirm_password": "new-password-456",
            },
        ).status_code
        == 303
    )
    client.cookies.clear()
    assert (
        client.post(
            "/admin/login", data={"email": "owner@example.com", "password": "new-password-456"}, follow_redirects=False
        ).status_code
        == 303
    )


def test_unknown_ids_are_404(browser):
    assert browser.get("/admin/firms/not-a-uuid").status_code == 404
    assert browser.get("/admin/plans/00000000-0000-0000-0000-000000000000").status_code == 404
