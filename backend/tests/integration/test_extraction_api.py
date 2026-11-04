import io

import openpyxl
import pytest

from tests.factories import make_invoice_pdf, make_pdf


def upload(api, pdf: bytes, name: str = "inv.pdf") -> str:
    response = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents", files={"file": (name, pdf, "application/pdf")}
    )
    assert response.status_code == 202, response.text
    return response.json()["document_id"]


def extract(api, doc_id: str, **body):
    response = api.post(f"/api/v1/documents/{doc_id}/extraction", json=body)
    assert response.status_code == 202, response.text
    # TestClient runs background tasks before returning, so the run has finished.
    return api.get(f"/api/v1/documents/{doc_id}/extraction").json()


@pytest.mark.parametrize("seed, scanned", [(1, False), (2, False), (3, True), (5, True)])
def test_invoice_values_are_read_and_valid(api, seed, scanned):
    pdf, truth = make_invoice_pdf(seed, scanned)
    result = extract(api, upload(api, pdf))
    values = result["values"]
    assert result["status"] == "needs_review", result
    assert result["issues"] == [], result["issues"]
    for key in ("vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin", "invoice_number", "invoice_date"):
        assert values[key] == truth[key], key
    for key in ("subtotal", "tax_total", "total"):
        assert abs(values[key] - truth[key]) <= 0.02, key


def test_wrong_total_is_flagged_and_blocks_approval(api):
    truth = make_invoice_pdf(4)[1]
    # Print a total that does not add up.
    import random

    from evaluation.invoices import draw, make_invoice

    invoice = make_invoice(4, random.Random(4))
    invoice["total"] += 500
    doc = draw(invoice, 4 % 3)
    doc_id = upload(api, doc.tobytes())
    result = extract(api, doc_id)
    assert [i["code"] for i in result["issues"]] == ["total_mismatch"]
    blocked = api.post(f"/api/v1/documents/{doc_id}/extraction/approve")
    assert blocked.status_code == 409 and "total" in blocked.json()["detail"].lower()

    # The reviewer fixes the number; the problem disappears and approval works.
    fixed = api.patch(f"/api/v1/documents/{doc_id}/extraction", json={"values": {"total": truth["total"]}})
    assert fixed.json()["issues"] == []
    assert api.post(f"/api/v1/documents/{doc_id}/extraction/approve").json()["status"] == "approved"


def test_editing_an_approved_extraction_reopens_review(api):
    pdf, _ = make_invoice_pdf(1)
    doc_id = upload(api, pdf)
    extract(api, doc_id)
    assert api.post(f"/api/v1/documents/{doc_id}/extraction/approve").json()["status"] == "approved"
    edited = api.patch(f"/api/v1/documents/{doc_id}/extraction", json={"values": {"invoice_number": "X-1"}}).json()
    assert edited["status"] == "needs_review" and edited["reviewed_at"] is None
    assert edited["values"]["invoice_number"] == "X-1"


def test_duplicate_invoice_is_detected_across_documents(api):
    pdf, _ = make_invoice_pdf(1)
    first, second = upload(api, pdf, "a.pdf"), upload(api, pdf, "b.pdf")
    assert extract(api, first)["issues"] == []
    issues = extract(api, second)["issues"]
    assert [i["code"] for i in issues] == ["duplicate"] and "a.pdf" in issues[0]["message"]


def test_model_that_returns_garbage_falls_back_to_rules(api):
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "mock", "label": "mock", "default_model": "mock-1"},
    ).json()["id"]
    pdf, truth = make_invoice_pdf(2)
    result = extract(api, upload(api, pdf), provider_id=provider, model="mock-1")
    assert result["status"] == "needs_review" and result["values"]["invoice_number"] == truth["invoice_number"]


def test_request_validation(api):
    doc_id = upload(api, make_invoice_pdf(1)[0])
    base = f"/api/v1/documents/{doc_id}/extraction"
    assert api.post(base, json={"schema_key": "nope"}).status_code == 422
    assert api.post(base, json={"model": "x"}).status_code == 422  # model without provider
    assert api.get(base).status_code == 404  # nothing run yet
    other_provider = "00000000-0000-0000-0000-000000000000"
    assert api.post(base, json={"provider_id": other_provider, "model": "x"}).status_code == 404


def test_document_without_invoice_fields_needs_review_with_missing_issues(api):
    result = extract(api, upload(api, make_pdf(["Minutes of the staff meeting. Nothing financial here."])))
    assert result["status"] == "needs_review"
    assert {i["code"] for i in result["issues"]} >= {"missing"}


def test_list_and_excel_export_contain_approved_only(api):
    approved, pending = upload(api, make_invoice_pdf(1)[0], "ok.pdf"), upload(api, make_invoice_pdf(2)[0], "wait.pdf")
    extract(api, approved)
    extract(api, pending)
    api.post(f"/api/v1/documents/{approved}/extraction/approve")
    ws = f"/api/v1/workspaces/{api.workspace_id}/extractions"
    assert {e["filename"] for e in api.get(ws).json()} == {"ok.pdf", "wait.pdf"}
    assert [e["filename"] for e in api.get(ws, params={"status": "approved"}).json()] == ["ok.pdf"]

    response = api.get(f"{ws}/export")
    assert response.status_code == 200 and "spreadsheetml" in response.headers["content-type"]
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][:3] == ("Vendor name", "Vendor GSTIN", "Buyer name")
    assert len(rows) == 2 and rows[1][-2] == "ok.pdf"
    assert isinstance(rows[1][rows[0].index("Total")], float)


def test_other_tenant_gets_404_on_every_extraction_route(api, make_tenant):
    doc_id = upload(api, make_invoice_pdf(1)[0])
    extract(api, doc_id)
    intruder = make_tenant("mallory")
    base = f"/api/v1/documents/{doc_id}/extraction"
    ws = f"/api/v1/workspaces/{api.workspace_id}/extractions"
    attempts = [
        intruder.get(base),
        intruder.post(base, json={}),
        intruder.patch(base, json={"values": {"total": 1}}),
        intruder.post(f"{base}/approve"),
        intruder.get(ws),
        intruder.get(f"{ws}/export"),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    assert api.get(base).json()["status"] == "needs_review"


def test_deleting_the_document_removes_its_extraction(api):
    doc_id = upload(api, make_invoice_pdf(1)[0])
    extract(api, doc_id)
    assert api.delete(f"/api/v1/documents/{doc_id}").status_code == 204
    assert api.get(f"/api/v1/workspaces/{api.workspace_id}/extractions").json() == []


def test_corrections_are_audited_with_before_and_after(api):
    pdf, _ = make_invoice_pdf(2)
    doc_id = upload(api, pdf)
    extract(api, doc_id)
    original_number = api.get(f"/api/v1/documents/{doc_id}/extraction").json()["values"]["invoice_number"]

    api.patch(f"/api/v1/documents/{doc_id}/extraction", json={"values": {"invoice_number": "INV-FIXED-1"}})
    api.patch(f"/api/v1/documents/{doc_id}/extraction", json={"values": {"invoice_number": "INV-FIXED-1"}})  # no-op

    entries = api.get(f"/api/v1/organizations/{api.org_id}/audit-logs", params={"action": "extraction.update"}).json()
    assert len(entries) == 1  # an edit that changes nothing is not logged
    entry = entries[0]
    assert entry["actor_email"] == api.email and entry["target_id"] == doc_id
    assert entry["details"]["changes"] == {"invoice_number": {"from": original_number, "to": "INV-FIXED-1"}}
