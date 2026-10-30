import uuid

from app.core.security import REFRESH, create_token


def creds(email, password="correct-horse-battery"):
    return {"email": email, "password": password}


def test_register_login_me(client):
    email = f"Ana-{uuid.uuid4().hex[:6]}@Example.com"
    registered = client.post("/api/v1/auth/register", json={**creds(email), "organization_name": "Acme"})
    assert registered.status_code == 201
    assert registered.json()["email"] == email.lower()
    assert "password" not in registered.text and "hash" not in registered.text

    tokens = client.post("/api/v1/auth/login", json=creds(email.upper())).json()  # email is case-insensitive
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] > 0

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
    assert me["email"] == email.lower()
    assert [(o["organization_name"], o["role"]) for o in me["organizations"]] == [("Acme", "owner")]


def test_duplicate_email_and_weak_password(client):
    email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    assert client.post("/api/v1/auth/register", json=creds(email)).status_code == 201
    assert client.post("/api/v1/auth/register", json=creds(email.upper())).status_code == 409
    assert client.post("/api/v1/auth/register", json=creds("x@example.com", "short")).status_code == 422


def test_wrong_password_and_unknown_email_look_the_same(client):
    email = f"pw-{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json=creds(email))
    wrong = client.post("/api/v1/auth/login", json=creds(email, "wrong-password"))
    unknown = client.post("/api/v1/auth/login", json=creds("nobody@example.com"))
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password"}


def test_protected_routes_need_a_valid_access_token(client, api):
    url = f"/api/v1/workspaces/{api.workspace_id}/documents"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401

    # A refresh token must not work as an access token.
    refresh_as_access = {"Authorization": f"Bearer {api.tokens['refresh_token']}"}
    assert client.get(url, headers=refresh_as_access).status_code == 401

    # A token signed with another secret is rejected.
    import jwt

    forged = jwt.encode({"sub": api.user_id, "type": "access", "jti": str(uuid.uuid4()), "exp": 9999999999}, "x" * 32)
    assert client.get(url, headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert api.get(url).status_code == 200


def test_refresh_rotates_and_old_refresh_token_dies(client, api):
    old = api.tokens["refresh_token"]
    new = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert new.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old}).status_code == 401  # replay
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new.json()["refresh_token"]}).status_code == 200


def test_logout_revokes_refresh_token(client, api):
    token = api.tokens["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": token}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_refresh_token_not_issued_by_us_is_rejected(client, api):
    # Validly signed, but there is no session row for this jti.
    token, _ = create_token(uuid.UUID(api.user_id), REFRESH)
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401
