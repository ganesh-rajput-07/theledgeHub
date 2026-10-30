from pathlib import Path

import pytest

from app.core.config import get_settings
from tests.factories import make_pdf

POLICY = ["Leave Policy. Every employee is entitled to 20 days of paid leave per calendar year."]


@pytest.fixture
def team(make_tenant):
    owner, member = make_tenant("owner"), make_tenant("member")
    added = owner.post(f"/api/v1/organizations/{owner.org_id}/members", json={"email": member.email})
    assert added.status_code == 201 and added.json()["role"] == "member"
    return owner, member


def upload(tenant, workspace_id, name="policy.pdf"):
    return tenant.post(
        f"/api/v1/workspaces/{workspace_id}/documents", files={"file": (name, make_pdf(POLICY), "application/pdf")}
    ).json()["document_id"]


def test_member_can_use_the_workspace(team):
    owner, member = team
    ws = owner.workspace_id
    orgs = {o["id"]: o["role"] for o in member.get("/api/v1/organizations").json()}
    assert orgs[owner.org_id] == "member"

    doc = upload(member, ws)
    assert member.get(f"/api/v1/documents/{doc}/status").json()["status"] == "completed"
    assert member.post(f"/api/v1/workspaces/{ws}/search", json={"query": "paid leave"}).json()["results"]

    provider = owner.post(
        f"/api/v1/organizations/{owner.org_id}/providers",
        json={"provider": "mock", "label": "Shared", "default_model": "mock-1"},
    ).json()["id"]
    # Members can use the org's key without ever seeing it.
    conversation = member.post(f"/api/v1/workspaces/{ws}/conversations", json={"provider_id": provider}).json()["id"]
    answer = member.post(f"/api/v1/conversations/{conversation}/messages", json={"question": "How much leave?"})
    assert answer.json()["grounded"] is True


def test_member_cannot_manage(team):
    owner, member = team
    org = owner.org_id
    assert member.post(f"/api/v1/organizations/{org}/workspaces", json={"name": "New"}).status_code == 403
    assert member.post(f"/api/v1/organizations/{org}/members", json={"email": owner.email}).status_code == 403
    assert (
        member.post(
            f"/api/v1/organizations/{org}/providers", json={"provider": "mock", "label": "x", "default_model": "mock-1"}
        ).status_code
        == 403
    )
    assert member.delete(f"/api/v1/workspaces/{owner.workspace_id}").status_code == 403

    provider = owner.post(
        f"/api/v1/organizations/{org}/providers", json={"provider": "mock", "label": "k", "default_model": "mock-1"}
    ).json()["id"]
    assert member.get(f"/api/v1/providers/{provider}").status_code == 200
    assert member.patch(f"/api/v1/providers/{provider}", json={"label": "x"}).status_code == 403
    assert member.delete(f"/api/v1/providers/{provider}").status_code == 403


def test_document_delete_rules(team):
    owner, member = team
    owners_doc = upload(owner, owner.workspace_id, "owner.pdf")
    members_doc = upload(member, owner.workspace_id, "member.pdf")
    assert member.delete(f"/api/v1/documents/{owners_doc}").status_code == 403
    assert member.delete(f"/api/v1/documents/{members_doc}").status_code == 204
    assert owner.delete(f"/api/v1/documents/{upload(member, owner.workspace_id)}").status_code == 204


def test_conversations_are_private(team):
    owner, member = team
    provider = owner.post(
        f"/api/v1/organizations/{owner.org_id}/providers",
        json={"provider": "mock", "label": "k", "default_model": "mock-1"},
    ).json()["id"]
    mine = member.post(f"/api/v1/workspaces/{owner.workspace_id}/conversations", json={"provider_id": provider})
    conversation = mine.json()["id"]
    assert owner.get(f"/api/v1/conversations/{conversation}").status_code == 404
    assert conversation not in {
        c["id"] for c in owner.get(f"/api/v1/workspaces/{owner.workspace_id}/conversations").json()
    }
    assert conversation in {
        c["id"] for c in member.get(f"/api/v1/workspaces/{owner.workspace_id}/conversations").json()
    }


def test_removed_member_loses_access_immediately(team):
    owner, member = team
    doc = upload(member, owner.workspace_id)
    assert owner.delete(f"/api/v1/organizations/{owner.org_id}/members/{member.user_id}").status_code == 204
    assert member.get(f"/api/v1/workspaces/{owner.workspace_id}").status_code == 404
    assert member.get(f"/api/v1/documents/{doc}").status_code == 404


def test_last_owner_cannot_be_removed_and_admins_cannot_add_owners(team, make_tenant):
    owner, _member = team
    assert owner.delete(f"/api/v1/organizations/{owner.org_id}/members/{owner.user_id}").status_code == 409

    admin = make_tenant("admin")
    owner.post(f"/api/v1/organizations/{owner.org_id}/members", json={"email": admin.email, "role": "admin"})
    escalate = admin.post(
        f"/api/v1/organizations/{owner.org_id}/members", json={"email": make_tenant("x").email, "role": "owner"}
    )
    assert escalate.status_code == 403
    assert admin.delete(f"/api/v1/organizations/{owner.org_id}/members/{owner.user_id}").status_code == 403


def test_deleting_workspace_removes_documents_and_files(team):
    owner, _ = team
    ws = owner.post(f"/api/v1/organizations/{owner.org_id}/workspaces", json={"name": "Temp"}).json()["id"]
    doc = upload(owner, ws)
    stored = list(Path(get_settings().storage_dir).glob(f"{doc}.*"))
    assert stored

    assert owner.delete(f"/api/v1/workspaces/{ws}").status_code == 204
    assert owner.get(f"/api/v1/documents/{doc}").status_code == 404
    assert not stored[0].exists()
