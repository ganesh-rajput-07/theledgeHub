"""Organization A's data must be invisible to organization B through every route."""

import pytest

from tests.factories import make_pdf

SECRET = ["Project Falcon. The confidential acquisition price is INR 950 crore, approved by the board."]


@pytest.fixture
def tenants(make_tenant):
    a, b = make_tenant("alice"), make_tenant("bob")
    doc = a.post(
        f"/api/v1/workspaces/{a.workspace_id}/documents",
        files={"file": ("falcon.pdf", make_pdf(SECRET), "application/pdf")},
    ).json()["document_id"]
    provider = a.post(
        f"/api/v1/organizations/{a.org_id}/providers",
        json={"provider": "mock", "label": "A mock", "default_model": "mock-1"},
    ).json()["id"]
    conversation = a.post(f"/api/v1/workspaces/{a.workspace_id}/conversations", json={"provider_id": provider}).json()[
        "id"
    ]
    message = a.post(
        f"/api/v1/conversations/{conversation}/messages", json={"question": "What is the acquisition price?"}
    ).json()
    assert message["grounded"], message
    return a, b, {"doc": doc, "provider": provider, "conversation": conversation, "message": message["message_id"]}


def test_other_tenant_gets_404_everywhere(tenants):
    a, b, ids = tenants
    ws, org = a.workspace_id, a.org_id
    attempts = [
        b.get(f"/api/v1/organizations/{org}"),
        b.get(f"/api/v1/organizations/{org}/members"),
        b.get(f"/api/v1/organizations/{org}/workspaces"),
        b.get(f"/api/v1/organizations/{org}/providers"),
        b.post(f"/api/v1/organizations/{org}/members", json={"email": b.email}),
        b.get(f"/api/v1/workspaces/{ws}"),
        b.get(f"/api/v1/workspaces/{ws}/documents"),
        b.post(f"/api/v1/workspaces/{ws}/documents", files={"file": ("x.txt", b"hi", "text/plain")}),
        b.post(f"/api/v1/workspaces/{ws}/search", json={"query": "acquisition price"}),
        b.get(f"/api/v1/workspaces/{ws}/conversations"),
        b.delete(f"/api/v1/workspaces/{ws}"),
        b.get(f"/api/v1/documents/{ids['doc']}"),
        b.get(f"/api/v1/documents/{ids['doc']}/status"),
        b.get(f"/api/v1/documents/{ids['doc']}/chunks"),
        b.post(f"/api/v1/documents/{ids['doc']}/reprocess"),
        b.delete(f"/api/v1/documents/{ids['doc']}"),
        b.get(f"/api/v1/providers/{ids['provider']}"),
        b.patch(f"/api/v1/providers/{ids['provider']}", json={"label": "pwned"}),
        b.post(f"/api/v1/providers/{ids['provider']}/validate"),
        b.delete(f"/api/v1/providers/{ids['provider']}"),
        b.get(f"/api/v1/conversations/{ids['conversation']}"),
        b.get(f"/api/v1/conversations/{ids['conversation']}/messages"),
        b.post(f"/api/v1/conversations/{ids['conversation']}/messages", json={"question": "price?"}),
        b.delete(f"/api/v1/conversations/{ids['conversation']}"),
        b.get(f"/api/v1/messages/{ids['message']}/citations"),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    assert "950" not in "".join(r.text for r in attempts)

    # And nothing was changed or deleted by those attempts.
    assert a.get(f"/api/v1/documents/{ids['doc']}").status_code == 200
    assert a.get(f"/api/v1/providers/{ids['provider']}").json()["label"] == "A mock"
    assert len(a.get(f"/api/v1/conversations/{ids['conversation']}/messages").json()) == 2


def test_search_never_crosses_tenants(tenants):
    _a, b, ids = tenants
    # B uploads its own unrelated document, then searches with A's exact wording.
    b.post(
        f"/api/v1/workspaces/{b.workspace_id}/documents",
        files={"file": ("menu.pdf", make_pdf(["Cafeteria menu. Monday is pasta day."]), "application/pdf")},
    )
    results = b.post(
        f"/api/v1/workspaces/{b.workspace_id}/search", json={"query": "confidential acquisition price Project Falcon"}
    ).json()["results"]
    assert all(r["filename"] == "menu.pdf" for r in results)

    # Naming A's document ID explicitly doesn't help either.
    leaked = b.post(
        f"/api/v1/workspaces/{b.workspace_id}/search", json={"query": "acquisition price", "document_ids": [ids["doc"]]}
    )
    assert leaked.status_code == 400 and "950" not in leaked.text


def test_cannot_borrow_another_tenants_key_or_documents(tenants):
    _a, b, ids = tenants
    # B tries to start a conversation billed to A's provider key.
    assert (
        b.post(f"/api/v1/workspaces/{b.workspace_id}/conversations", json={"provider_id": ids["provider"]}).status_code
        == 404
    )
    # B tries to scope its own conversation to A's document.
    own = b.post(
        f"/api/v1/organizations/{b.org_id}/providers",
        json={"provider": "mock", "label": "B mock", "default_model": "mock-1"},
    ).json()["id"]
    response = b.post(
        f"/api/v1/workspaces/{b.workspace_id}/conversations", json={"provider_id": own, "document_ids": [ids["doc"]]}
    )
    assert response.status_code == 400

    conversation = b.post(f"/api/v1/workspaces/{b.workspace_id}/conversations", json={"provider_id": own}).json()["id"]
    ask = b.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"question": "What is the acquisition price?", "document_ids": [ids["doc"]]},
    )
    assert ask.status_code == 400
    answer = b.post(
        f"/api/v1/conversations/{conversation}/messages", json={"question": "What is the acquisition price?"}
    ).json()
    assert answer["status"] == "not_found" and "950" not in answer["answer"]
