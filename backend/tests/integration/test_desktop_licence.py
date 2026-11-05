"""Installed (desktop) mode: sign-in goes through the licence server and every API call needs a valid lease."""

import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from app.core.config import get_settings
from app.licensing import lease as leases
from app.licensing import service as licensing
from app.licensing.machine import machine_id
from app.models import Membership, Organization, Role, User

CTX = {"firm": "", "domain": ""}  # fresh firm and email domain per test (the test database is shared)
PRIVATE_KEY = Ed25519PrivateKey.generate()


def make_lease(email=None, role="owner", ttl=24 * 3600, key=PRIVATE_KEY, machine=None, **extra):
    now = int(time.time())
    email = email or f"owner@{CTX['domain']}"
    claims = {
        "sub": str(uuid.uuid4()),
        "mid": leases.machine_hash(machine or machine_id()),
        "firm": {"id": CTX["firm"], "name": "Shah & Associates", "reference": "KH-12345"},
        "user": {"email": email, "name": "Rakesh Shah", "role": role},
        "plan": {"code": "team", "name": "Team", "invoice_limit": None},
        "computers": 3,
        "ends_on": "2026-12-04",
        "trial": False,
        "iss": leases.ISSUER,
        "aud": leases.AUDIENCE,
        "iat": now,
        "nbf": now - 60,
        "exp": now + ttl,
        "ttl": ttl,
        "jti": str(uuid.uuid4()),
    } | extra
    return jwt.encode(claims, key, algorithm="EdDSA")


@pytest.fixture
def desktop(monkeypatch, tmp_path):
    """Desktop mode with a test licence key; the licence server is replaced by `server.reply`."""
    public = tmp_path / "licence_public_key.pem"
    public.write_bytes(
        PRIVATE_KEY.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "licence_mode", "desktop")
    monkeypatch.setattr(settings, "licence_public_key_file", str(public))
    leases.public_key.cache_clear()
    leases.clear()
    CTX.update(firm=str(uuid.uuid4()), domain=f"{uuid.uuid4().hex[:8]}.example")

    class Server:
        reply = staticmethod(lambda email, password: make_lease(email=email))
        calls = 0

    def fake_request(email, password):
        Server.calls += 1
        result = Server.reply(email, password)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(licensing, "request_lease", fake_request)
    yield Server
    leases.clear()
    leases.public_key.cache_clear()


@pytest.fixture
def db_session():
    from app.database.session import SessionLocal

    with SessionLocal() as session:
        yield session


def login(client, email=None, password="any-password-123"):
    email = email or f"owner@{CTX['domain']}"
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_desktop_login_creates_local_firm_and_user(client, desktop, db_session):
    response = login(client)
    assert response.status_code == 200, response.text
    me = client.get("/api/v1/auth/me", headers=bearer(response)).json()
    assert me["email"] == f"owner@{CTX['domain']}"
    assert [o["organization_name"] for o in me["organizations"]] == ["Shah & Associates"]
    org = db_session.scalar(select(Organization).where(Organization.licence_firm_id == CTX["firm"]))
    assert org is not None
    status = client.get("/api/v1/licence/status").json()
    assert status["active"] and status["firm"] == "Shah & Associates" and status["seconds_left"] > 23 * 3600


def test_colleague_joins_the_same_firm_with_their_role(client, desktop, db_session):
    login(client)
    desktop.reply = staticmethod(lambda email, password: make_lease(email=email, role="member"))
    assert login(client, email=f"asha@{CTX['domain']}").status_code == 200
    org = db_session.scalar(select(Organization).where(Organization.licence_firm_id == CTX["firm"]))
    roles = {
        db_session.get(User, m.user_id).email: m.role
        for m in db_session.scalars(select(Membership).where(Membership.organization_id == org.id))
    }
    assert roles == {f"owner@{CTX['domain']}": Role.OWNER, f"asha@{CTX['domain']}": Role.MEMBER}


def test_local_password_and_registration_are_not_used(client, desktop, db_session):
    login(client)
    user = db_session.scalar(select(User).where(User.email == f"owner@{CTX['domain']}"))
    assert user.password_hash  # random: only the licence server checks passwords
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@x.example", "password": "long-password-1", "full_name": "X", "organization_name": "X"},
    )
    assert response.status_code == 403


def test_everything_stops_when_the_lease_runs_out(client, desktop, monkeypatch):
    headers = bearer(login(client))
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    start = leases.uptime()
    monkeypatch.setattr(leases, "uptime", lambda: start + 24 * 3600 + 1)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 402 and response.headers["x-licence-code"] == "licence_required"
    assert client.get("/api/v1/licence/status").json()["active"] is False
    assert login(client).status_code == 200  # signing in online again works


def test_changing_the_wall_clock_does_not_extend_the_lease(client, desktop, monkeypatch):
    login(client)
    left = leases.current().seconds_left
    monkeypatch.setattr(time, "time", lambda: 0.0)  # clock set back to 1970
    assert abs(leases.current().seconds_left - left) <= 1


def test_forged_or_foreign_leases_are_rejected(client, desktop):
    desktop.reply = staticmethod(lambda e, p: make_lease(email=e, key=Ed25519PrivateKey.generate()))
    response = login(client)
    assert response.status_code == 403 and response.headers["x-licence-code"] == "lease_invalid"
    desktop.reply = staticmethod(lambda e, p: make_lease(email=e, machine="another-computer"))
    assert login(client).status_code == 403
    desktop.reply = staticmethod(lambda e, p: make_lease(email=e, ttl=30 * 24 * 3600))
    assert login(client).status_code == 403  # longer than any lease the server issues
    assert leases.current() is None


def test_licence_server_refusals_are_shown_to_the_user(client, desktop):
    desktop.reply = staticmethod(
        lambda e, p: licensing.LicenceError(
            402, "expired", "Your subscription ended on 04 Dec 2026. Renew at https://example/account"
        )
    )
    response = login(client)
    assert response.status_code == 402
    assert response.json()["detail"].startswith("Your subscription ended")
    assert response.headers["x-licence-code"] == "expired"


def test_another_local_account_cannot_use_someone_elses_lease(client, desktop):
    owner = bearer(login(client))
    desktop.reply = staticmethod(lambda email, password: make_lease(email=email, role="member"))
    login(client, email=f"asha@{CTX['domain']}")  # the lease now belongs to Asha
    assert client.get("/api/v1/auth/me", headers=owner).status_code == 401


def test_sign_out_forgets_the_lease(client, desktop):
    response = login(client)
    client.post("/api/v1/auth/logout", json={"refresh_token": response.json()["refresh_token"]})
    assert client.get("/api/v1/auth/me", headers=bearer(response)).status_code == 402


def test_licence_server_unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(licensing.LicenceError) as caught:
        licensing.request_lease("a@b.example", "pw")
    assert caught.value.status == 503 and "internet" in caught.value.message


def test_licence_server_error_reply_is_passed_through(monkeypatch):
    request = httpx.Request("POST", "http://licence/api/app/v1/login")
    reply = httpx.Response(
        403, json={"code": "computer_limit", "message": "All 3 computers are in use."}, request=request
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: reply)
    with pytest.raises(licensing.LicenceError) as caught:
        licensing.request_lease("a@b.example", "pw")
    assert (caught.value.status, caught.value.code) == (403, "computer_limit")


def test_off_mode_needs_no_licence(client):
    assert client.get("/api/v1/licence/status").json() == {"mode": "off", "active": True}
