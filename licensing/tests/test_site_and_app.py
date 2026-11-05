import re
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app import lease, money, services
from app.config import get_settings
from app.models import Computer, CustomerUser, Firm, PaymentClaim, Plan

PASSWORD = "customer-password-1"
MACHINE = "machine-guid-0001-aaaa"


@pytest.fixture
def plans(db, admin):
    def make(code, name, price, computers, **extra):
        data = (
            dict(
                name=name,
                code=code,
                description=f"{name} plan",
                price_paise=price,
                billing_months=1,
                computers_included=computers,
                extra_computer_paise=69900,
                max_users=None,
                invoice_limit=None,
                is_active=True,
                is_public=True,
                sort_order=0,
            )
            | extra
        )
        return services.save_plan(db, admin, None, data, None)

    return {
        "solo": make("solo", "Solo", 99900, 1),
        "team": make("team", "Team", 249900, 2, max_users=3),
        "secret": make("secret", "Secret deal", 100, 1, is_public=False),
        "old": make("old", "Old plan", 5000, 1, is_active=False),
    }


def register(client, email="shah@example.com", plan="team", **overrides):
    data = {
        "plan": plan,
        "firm_name": "Shah & Associates",
        "name": "Rakesh Shah",
        "email": email,
        "mobile": "98250 12345",
        "city": "Surat",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "terms": "on",
    } | overrides
    return client.post("/register", data=data, follow_redirects=False)


def csrf(client):
    return re.search(r'name="csrf" value="([^"]+)"', client.get("/account").text).group(1)


def activate(db, admin, email="shah@example.com", plan_code="team", computers=None, ends_on=None):
    user = db.scalar(select(CustomerUser).where(CustomerUser.email == email))
    firm = db.get(Firm, user.firm_id)
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    services.record_payment(
        db,
        admin,
        firm,
        plan=plan,
        computers=computers or plan.computers_included,
        periods=1,
        amount_paise=294882,
        method="upi",
        utr="UTR1",
        paid_on=money.today(),
        note="",
        ip=None,
    )
    if ends_on:
        db.refresh(firm)
        firm.subscription.ends_on = ends_on
        db.commit()
    return firm


def app_login(client, email="shah@example.com", password=PASSWORD, machine=MACHINE, version="1.0.0", name="PC-1"):
    return client.post(
        "/api/app/v1/login",
        json={
            "email": email,
            "password": password,
            "machine_id": machine,
            "machine_name": name,
            "app_version": version,
        },
    )


# ------------------------------------------------------------------ public website


def test_pricing_shows_only_public_plans_on_sale(client, plans):
    page = client.get("/").text
    assert "Solo" in page and "Team" in page
    assert "Secret deal" not in page and "Old plan" not in page
    assert "₹1,178.82 incl. GST" in page  # 999 + 18%


def test_register_creates_pending_firm_and_shows_how_to_pay(client, plans, db):
    response = register(client)
    assert response.status_code == 303 and response.headers["location"] == "/account"
    firm = db.scalar(select(Firm))
    owner = db.scalar(select(CustomerUser))
    assert (owner.role, owner.firm_id, firm.requested_plan_id) == ("owner", firm.id, plans["team"].id)
    page = client.get("/account").text
    assert "Pending payment" in page and firm.reference in page
    assert "₹2,948.82" in page  # team price incl. GST
    assert "Download for Windows" not in page


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirm_password": "different-password"},
        {"password": "short", "confirm_password": "short"},
        {"terms": ""},
        {"mobile": ""},
        {"plan": "secret"},
        {"plan": "old"},
        {"email": "bad"},
        {"name": ""},
    ],
)
def test_register_validation(client, plans, overrides):
    assert register(client, **overrides).status_code == 400


def test_register_duplicate_email(client, plans):
    register(client)
    client.cookies.clear()
    assert register(client, email="SHAH@example.com").status_code == 400


def test_register_rate_limit(client, plans, monkeypatch):
    monkeypatch.setattr(get_settings(), "register_ip_per_hour", 2)
    assert register(client, email="a@example.com").status_code == 303
    client.cookies.clear()
    assert register(client, email="b@example.com").status_code == 303
    client.cookies.clear()
    assert register(client, email="c@example.com").status_code == 429


def test_login_logout_and_protected_pages(client, plans):
    register(client)
    client.cookies.clear()
    for url in ("/account", "/account/team", "/account/computers", "/account/password"):
        assert client.get(url, follow_redirects=False).headers["location"] == "/login"
    assert client.post("/login", data={"email": "shah@example.com", "password": "wrong"}).status_code == 401
    assert (
        client.post(
            "/login", data={"email": "shah@example.com", "password": PASSWORD}, follow_redirects=False
        ).status_code
        == 303
    )
    assert client.post("/logout", data={"csrf": csrf(client)}, follow_redirects=False).status_code == 303
    assert client.get("/account", follow_redirects=False).status_code == 303


def test_posts_need_csrf(client, plans):
    register(client)
    assert client.post("/account/paid", data={"amount": "1"}).status_code == 403


# ------------------------------------------------------------------ "I have paid" → admin confirms


def test_payment_claim_flow(client, plans, db, admin):
    register(client)
    response = client.post(
        "/account/paid",
        data={
            "csrf": csrf(client),
            "amount": "2948.82",
            "method": "upi",
            "utr": "4309 1234".replace(" ", ""),
            "paid_on": money.today().isoformat(),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    claim = db.scalar(select(PaymentClaim))
    assert (claim.status, claim.amount_paise, claim.utr) == ("open", 294882, "43091234")
    assert "We're checking 1 payment" in client.get("/account").text

    from tests.conftest import Browser

    admin_client = type(client)(client.app)
    browser = Browser(admin_client)
    assert "Customers say they've paid" in browser.get("/admin/").text
    firm = db.scalar(select(Firm))
    prefilled = browser.get(f"/admin/firms/{firm.id}?claim={claim.id}").text
    assert 'value="2948.82"' in prefilled and 'name="claim_id"' in prefilled
    response = browser.post(
        f"/admin/firms/{firm.id}/payment",
        {
            "plan_id": str(plans["team"].id),
            "computers": "2",
            "periods": "1",
            "amount": "2948.82",
            "method": "upi",
            "utr": claim.utr,
            "paid_on": money.today().isoformat(),
            "claim_id": str(claim.id),
        },
    )
    assert response.status_code == 303
    db.refresh(claim)
    assert claim.status == "confirmed"

    page = client.get("/account").text
    assert "Active" in page and "installer will be available here soon" in page
    services.save_settings(
        db, admin, {"download_url": "https://downloads.example/KnowledgeHub-Setup.exe", "latest_version": "1.0.0"}, None
    )
    assert "https://downloads.example/KnowledgeHub-Setup.exe" in client.get("/account").text


def test_payment_claim_validation(client, plans):
    register(client)
    token = csrf(client)
    base = {"csrf": token, "amount": "100", "method": "upi", "utr": "ABC12345", "paid_on": money.today().isoformat()}
    assert client.post("/account/paid", data=base | {"utr": "x"}).status_code == 400
    assert client.post("/account/paid", data=base | {"method": "cash"}).status_code == 400
    future = (money.today() + timedelta(days=1)).isoformat()
    assert client.post("/account/paid", data=base | {"paid_on": future}).status_code == 400
    assert client.post("/account/paid", data=base | {"amount": "0"}).status_code == 400


def test_download_hidden_when_not_paid(client, plans, db, admin):
    services.save_settings(db, admin, {"download_url": "https://downloads.example/setup.exe"}, None)
    register(client)
    assert "downloads.example" not in client.get("/account").text


# ------------------------------------------------------------------ team and computers


def test_team_management(client, plans, db, admin):
    register(client)
    activate(db, admin)
    token = csrf(client)
    add = {"csrf": token, "name": "Asha", "email": "asha@example.com", "role": "member", "password": "member-pass-123"}
    assert client.post("/account/team", data=add, follow_redirects=False).status_code == 303
    assert client.post("/account/team", data=add | {"email": "x@example.com", "role": "owner"}).status_code == 400
    assert (
        client.post("/account/team", data=add | {"email": "b@example.com"}, follow_redirects=False).status_code == 303
    )
    # Team plan allows 3 people: owner + 2.
    assert client.post("/account/team", data=add | {"email": "c@example.com"}).status_code == 400
    owner = db.scalar(select(CustomerUser).where(CustomerUser.role == "owner"))
    client.post(f"/account/team/{owner.id}", data={"csrf": token, "active": "0"})
    db.refresh(owner)
    assert owner.is_active

    # A member can't manage the team.
    member_client = type(client)(client.app)
    member_client.post("/login", data={"email": "asha@example.com", "password": "member-pass-123"})
    assert (
        member_client.post(
            "/account/team", data=add | {"csrf": csrf(member_client), "email": "d@example.com"}
        ).status_code
        == 400
    )


def test_cannot_touch_another_firms_people_or_computers(client, plans, db, admin):
    register(client, email="other@example.com")
    other = db.scalar(select(CustomerUser).where(CustomerUser.email == "other@example.com"))
    computer = Computer(firm_id=other.firm_id, machine_hash="b" * 64, name="Their PC")
    db.add(computer)
    db.commit()
    client.cookies.clear()
    register(client)
    token = csrf(client)
    assert client.post(f"/account/team/{other.id}", data={"csrf": token, "active": "0"}).status_code == 404
    assert client.post(f"/account/computers/{computer.id}/remove", data={"csrf": token}).status_code == 404
    assert client.post(f"/account/team/{uuid.uuid4()}", data={"csrf": token, "active": "0"}).status_code == 404


def test_self_service_computer_removal_is_limited(client, plans, db, admin):
    services.save_settings(db, admin, {"computer_changes_per_month": "1"}, None)
    register(client)
    firm = activate(db, admin)
    pcs = [Computer(firm_id=firm.id, machine_hash=c * 64, name=f"PC {c}") for c in "cd"]
    db.add_all(pcs)
    db.commit()
    ids = [pc.id for pc in pcs]
    token = csrf(client)
    client.post(f"/account/computers/{ids[0]}/remove", data={"csrf": token})
    client.post(f"/account/computers/{ids[1]}/remove", data={"csrf": token})
    db.expire_all()
    assert db.get(Computer, ids[0]) is None and db.get(Computer, ids[1]) is not None


# ------------------------------------------------------------------ desktop app login API


def test_app_login_requires_active_subscription(client, plans, public_key):
    register(client)
    response = app_login(client)
    assert response.status_code == 402 and response.json()["code"] == "no_subscription"
    assert "https://licence.example/account" in response.json()["message"]


def test_app_login_issues_verifiable_lease(client, plans, db, admin, public_key):
    register(client)
    activate(db, admin)
    response = app_login(client)
    assert response.status_code == 200, response.text
    body = response.json()
    claims = lease.verify(body["lease"], public_key, lease.machine_hash(MACHINE))
    assert claims["firm"]["name"] == "Shah & Associates" and claims["plan"]["code"] == "team"
    assert claims["exp"] - claims["iat"] == 24 * 3600 and claims["ttl"] == 24 * 3600
    assert body["subscription"]["status"] == "active" and body["user"]["role"] == "owner"
    computer = db.scalar(select(Computer))
    assert (computer.name, computer.app_version) == ("PC-1", "1.0.0")
    assert computer.machine_hash != MACHINE  # only a hash is stored
    assert client.get("/api/app/v1/public-key").text == public_key


def test_lease_rejects_tampering_and_other_computers(client, plans, db, admin, public_key):
    register(client)
    activate(db, admin)
    token = app_login(client).json()["lease"]
    with pytest.raises(jwt.InvalidTokenError):
        lease.verify(token, public_key, lease.machine_hash("another-machine-id-123"))
    header, payload, signature = token.split(".")
    forged = jwt.utils.base64url_encode(jwt.utils.base64url_decode(payload).replace(b'"team"', b'"firm"')).decode()
    with pytest.raises(jwt.InvalidTokenError):
        lease.verify(f"{header}.{forged}.{signature}", public_key, lease.machine_hash(MACHINE))


def test_lease_ends_with_the_subscription(client, plans, db, admin, public_key):
    register(client)
    activate(db, admin, ends_on=money.today())
    claims = lease.verify(app_login(client).json()["lease"], public_key, lease.machine_hash(MACHINE))
    midnight = lease.access_ends_at(money.today(), 0)
    assert claims["exp"] == int(midnight.timestamp())
    assert claims["exp"] <= int((datetime.now(UTC) + timedelta(hours=24)).timestamp())


def test_computer_limit(client, plans, db, admin, public_key):
    register(client)
    activate(db, admin)  # team: 2 computers
    assert app_login(client, machine="machine-one-1234567").status_code == 200
    assert app_login(client, machine="machine-two-1234567").status_code == 200
    third = app_login(client, machine="machine-three-123456")
    assert third.status_code == 403 and third.json()["code"] == "computer_limit"
    assert app_login(client, machine="machine-one-1234567").status_code == 200  # known computer still fine
    assert len(db.scalars(select(Computer)).all()) == 2


def test_app_login_refusals(client, plans, db, admin, public_key):
    register(client)
    assert app_login(client, password="wrong-password").json()["code"] == "invalid_credentials"
    firm = activate(db, admin, ends_on=money.today() - timedelta(days=1))
    assert app_login(client).json()["code"] == "expired"
    db.refresh(firm)
    firm.subscription.ends_on = money.today() + timedelta(days=10)
    firm.blocked = True
    db.commit()
    assert app_login(client).json()["code"] == "firm_blocked"
    firm.blocked = False
    db.commit()
    assert app_login(client).status_code == 200
    computer = db.scalar(select(Computer))
    computer.blocked = True
    db.commit()
    assert app_login(client).json()["code"] == "computer_blocked"
    services.save_settings(db, admin, {"min_app_version": "1.2"}, None)
    response = app_login(client, version="1.1.9")
    assert response.status_code == 426 and response.json()["code"] == "update_required"


def test_app_login_grace_period_and_trial(client, plans, db, admin, public_key):
    services.save_settings(db, admin, {"grace_days": "3"}, None)
    register(client)
    activate(db, admin, ends_on=money.today() - timedelta(days=1))
    body = app_login(client).json()
    assert body["subscription"]["status"] == "grace"
    claims = lease.verify(body["lease"], public_key, lease.machine_hash(MACHINE))
    assert claims["exp"] <= int(lease.access_ends_at(money.today() - timedelta(days=1), 3).timestamp())


def test_app_login_lockout_and_rate_limit(client, plans, db, admin, public_key, monkeypatch):
    register(client)
    activate(db, admin)
    for _ in range(5):
        app_login(client, password="wrong-password")
    response = app_login(client)
    assert response.status_code == 423 and response.json()["code"] == "locked"
    monkeypatch.setattr(get_settings(), "app_login_ip_per_15min", 0)
    assert app_login(client).status_code == 429


def test_app_login_without_signing_key(client, plans, db, admin, monkeypatch):
    register(client)
    activate(db, admin)

    def missing():
        raise lease.LeaseKeyMissing("no key")

    monkeypatch.setattr(lease, "private_key", missing)
    response = app_login(client)
    assert response.status_code == 503 and response.json()["code"] == "server_not_ready"


def test_app_login_validates_input(client):
    response = client.post(
        "/api/app/v1/login", json={"email": "a@b.c", "password": "x", "machine_id": "short", "app_version": "1"}
    )
    assert response.status_code == 422


def test_admin_payment_form_defaults_to_the_chosen_plans_computers(client, plans, db, admin):
    from tests.conftest import Browser

    register(client)  # chose Team (2 computers)
    firm = db.scalar(select(Firm))
    page = Browser(type(client)(client.app)).get(f"/admin/firms/{firm.id}").text
    assert re.search(r'name="computers" inputmode="numeric" value="2"', page)


def test_admin_resets_customer_password(client, plans, db, admin):
    from tests.conftest import Browser

    register(client)
    owner = db.scalar(select(CustomerUser))
    browser = Browser(type(client)(client.app))
    url = f"/admin/firms/{owner.firm_id}/users/{owner.id}/password"
    assert browser.post(url, {"password": "short"}).status_code == 400
    assert browser.post(url, {"password": "brand-new-password"}).status_code == 303
    client.cookies.clear()
    assert (
        client.post(
            "/login", data={"email": owner.email, "password": "brand-new-password"}, follow_redirects=False
        ).status_code
        == 303
    )
