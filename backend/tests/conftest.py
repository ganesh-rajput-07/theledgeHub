"""Points the app at a separate <db>_test database and a temp storage dir *before* app imports."""

import os
import tempfile
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

_main_url = make_url(Settings().database_url)
_test_url = make_url(os.environ.get("TEST_DATABASE_URL") or _main_url.set(database=f"{_main_url.database}_test"))
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="knowledgehub-test-storage-")
# The suite logs in hundreds of times from one client; brute-force tests lower these on purpose.
os.environ["LOGIN_IP_MAX_ATTEMPTS"] = "100000"
os.environ["REGISTER_IP_MAX_ATTEMPTS"] = "100000"
# Process uploads right after the response (TestClient waits for it); queue tests switch to "queue".
os.environ["INGESTION_MODE"] = "inline"
get_settings.cache_clear()


def _create_test_database() -> None:
    admin = _main_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_test_url.database,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{_test_url.database}"')


@pytest.fixture(scope="session", autouse=True)
def test_database():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.database.session import engine

    _create_test_database()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    from sqlalchemy import delete

    from app.database.session import SessionLocal
    from app.models import RateLimitEvent

    with SessionLocal() as db:
        db.execute(delete(RateLimitEvent))
        db.commit()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


class Tenant:
    """A registered user with their own organization and default workspace.
    Wraps the TestClient so every request carries this user's access token."""

    def __init__(self, client, email: str, password: str = "correct-horse-battery"):
        self.client, self.email, self.password = client, email, password
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Test User", "organization_name": f"Org {email}"},
        )
        assert response.status_code == 201, response.text
        self.user_id = response.json()["id"]
        self.tokens = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()
        self.org_id = self.get("/api/v1/organizations").json()[0]["id"]
        self.workspace_id = self.get(f"/api/v1/organizations/{self.org_id}/workspaces").json()[0]["id"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def _call(self, method, url, **kwargs):
        return self.client.request(method, url, headers={**self.headers, **kwargs.pop("headers", {})}, **kwargs)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._call("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._call("DELETE", url, **kwargs)


@pytest.fixture
def make_tenant(client):
    import uuid

    return lambda name="user": Tenant(client, f"{name}-{uuid.uuid4().hex[:8]}@example.com")


@pytest.fixture
def api(make_tenant):
    return make_tenant()
