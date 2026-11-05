"""Runs against a separate <db>_test database, rebuilt from the migrations once per test session."""

import os
import re
import tempfile
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.config import Settings, get_settings

_main = make_url(Settings().database_url)
_test = make_url(os.environ.get("TEST_DATABASE_URL") or _main.set(database=f"{_main.database}_test"))
os.environ["DATABASE_URL"] = _test.render_as_string(hide_password=False)
os.environ["COOKIE_SECURE"] = "false"  # TestClient talks plain http
KEY_FILE = Path(tempfile.mkdtemp(prefix="kh-lease-")) / "lease_private.pem"
os.environ["LEASE_PRIVATE_KEY_FILE"] = str(KEY_FILE)
os.environ["PUBLIC_URL"] = "https://licence.example"
get_settings.cache_clear()

PASSWORD = "admin-password-123"


@pytest.fixture(scope="session", autouse=True)
def database():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.db import engine

    admin_url = _main.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_test.database,)).fetchone():
            conn.execute(f'CREATE DATABASE "{_test.database}"')
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(database):
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE admin_users, admin_sessions, plans, firms, subscriptions, payments, computers, "
                "settings, audit_events, customer_users, customer_sessions, payment_claims CASCADE"
            )
        )
    from app.customers import limiter

    limiter.reset()
    yield


@pytest.fixture
def db():
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture
def admin(db):
    from app.models import AdminUser
    from app.security import hash_password

    user = AdminUser(email="owner@example.com", name="Owner", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


class Browser:
    """TestClient signed in as the admin; post() adds the page's CSRF token automatically."""

    def __init__(self, client):
        self.client = client
        response = client.post(
            "/admin/login", data={"email": "owner@example.com", "password": PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 303, response.text
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', client.get("/admin/").text).group(1)

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, data=None, **kw):
        return self.client.post(url, data={"csrf": self.csrf, **(data or {})}, follow_redirects=False, **kw)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def browser(client, admin):
    return Browser(client)


@pytest.fixture(scope="session")
def public_key():
    from app import lease

    return lease.generate_keypair(KEY_FILE)
