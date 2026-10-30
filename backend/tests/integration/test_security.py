import uuid

import pytest
from starlette.requests import Request

from app.core import rate_limit
from app.core.config import get_settings
from tests.factories import make_pdf

PASSWORD = "correct-horse-battery"


def login(client, email, password, **headers):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=headers)


# ---------------------------------------------------------------- brute-force protection


def test_account_locks_after_repeated_failures(client, api, make_tenant):
    for _ in range(get_settings().login_max_failures):
        assert login(client, api.email, "wrong-password").status_code == 401

    locked = login(client, api.email, PASSWORD)  # even the right password is refused now
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert login(client, api.email.upper(), PASSWORD).status_code == 429  # same account, any casing

    other = make_tenant("other")
    assert login(client, other.email, PASSWORD).status_code == 200  # other accounts unaffected


def test_successful_login_resets_failure_count(client, api):
    for _ in range(get_settings().login_max_failures - 1):
        login(client, api.email, "wrong-password")
    assert login(client, api.email, PASSWORD).status_code == 200
    for _ in range(get_settings().login_max_failures - 1):
        assert login(client, api.email, "wrong-password").status_code == 401


def test_ip_limit_cannot_be_dodged_with_spoofed_forwarded_for(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_ip_max_attempts", 3)
    statuses = [
        login(client, f"nobody{i}@example.com", "x", **{"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(5)
    ]
    # The test client is not a trusted proxy, so the fake IPs are ignored and all 5 count as one client.
    assert statuses == [401, 401, 401, 429, 429]


def test_register_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "register_ip_max_attempts", 2)
    codes = [
        client.post(
            "/api/v1/auth/register", json={"email": f"r{uuid.uuid4().hex[:6]}@example.com", "password": PASSWORD}
        ).status_code
        for _ in range(3)
    ]
    assert codes == [201, 201, 429]


def _request(peer: str, forwarded: str | None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


@pytest.mark.parametrize(
    ("peer", "forwarded", "expected"),
    [
        ("127.0.0.1", "203.0.113.7, 10.0.0.1", "203.0.113.7"),  # trusted proxy (the Next.js server)
        ("198.51.100.9", "203.0.113.7", "198.51.100.9"),  # untrusted peer: header ignored
        ("127.0.0.1", None, "127.0.0.1"),
    ],
)
def test_client_ip_trusts_forwarded_for_only_from_proxies(peer, forwarded, expected):
    rate_limit._trusted_networks.cache_clear()
    assert rate_limit.client_ip(_request(peer, forwarded)) == expected


# ---------------------------------------------------------------- audit trail


def audit(tenant, **params):
    response = tenant.get(f"/api/v1/organizations/{tenant.org_id}/audit-logs", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_security_relevant_actions_are_audited(client, api, make_tenant):
    login(client, api.email, "wrong-password")
    doc = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents",
        files={"file": ("audited.pdf", make_pdf(["Audit me."]), "application/pdf")},
    ).json()["document_id"]
    api.delete(f"/api/v1/documents/{doc}")
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "mock", "label": "Audited", "default_model": "mock-1"},
    ).json()["id"]
    api.patch(f"/api/v1/providers/{provider}", json={"label": "Renamed"})
    member = make_tenant("member")
    api.post(f"/api/v1/organizations/{api.org_id}/members", json={"email": member.email})
    ws = api.post(f"/api/v1/organizations/{api.org_id}/workspaces", json={"name": "Temp"}).json()["id"]
    api.delete(f"/api/v1/workspaces/{ws}")

    actions = [entry["action"] for entry in audit(api)]
    for expected in [
        "document.upload",
        "document.delete",
        "provider.create",
        "provider.update",
        "member.add",
        "workspace.create",
        "workspace.delete",
    ]:
        assert expected in actions, expected

    deleted = audit(api, action="document.delete")[0]
    assert deleted["actor_email"] == api.email and deleted["target_id"] == doc
    assert deleted["details"]["filename"] == "audited.pdf" and deleted["ip_address"]
    update = audit(api, action="provider.update")[0]
    assert update["details"] == {"changed": ["label"], "key_rotated": False}


def test_provider_key_never_appears_in_audit_log(api, monkeypatch):
    from app.llm import factory
    from app.llm.mock_provider import MockProvider

    class KeyedMock(MockProvider):
        name = "openai"

        def list_models(self):
            return ["gpt-test"]

    monkeypatch.setattr(factory, "build_provider", lambda *a, **k: KeyedMock())
    created = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-live-TOPSECRET-1234", "default_model": "gpt-test"},
    ).json()
    api.patch(f"/api/v1/providers/{created['id']}", json={"api_key": "sk-live-NEWSECRET-5678"})
    text = api.get(f"/api/v1/organizations/{api.org_id}/audit-logs").text
    assert "SECRET" not in text and '"key_rotated":true' in text


def test_audit_log_is_for_managers_of_that_org_only(api, make_tenant):
    member, outsider = make_tenant("member"), make_tenant("outsider")
    api.post(f"/api/v1/organizations/{api.org_id}/members", json={"email": member.email})
    assert member.get(f"/api/v1/organizations/{api.org_id}/audit-logs").status_code == 403
    assert outsider.get(f"/api/v1/organizations/{api.org_id}/audit-logs").status_code == 404


def test_mock_provider_is_disabled_in_production(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    response = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "mock", "label": "nope", "default_model": "mock-1"},
    )
    assert response.status_code == 400
    assert "disabled in production" in response.json()["detail"]
