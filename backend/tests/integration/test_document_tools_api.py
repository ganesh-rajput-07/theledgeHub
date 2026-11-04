import hashlib

import pymupdf

from tests.factories import make_invoice_pdf, make_pdf
from tests.integration.test_extraction_api import extract


def upload(tenant, data: bytes, name: str, mime: str = "application/pdf"):
    return tenant.post(f"/api/v1/workspaces/{tenant.workspace_id}/documents", files={"file": (name, data, mime)})


def upload_id(tenant, data: bytes, name: str = "doc.pdf") -> str:
    response = upload(tenant, data, name)
    assert response.status_code == 202, response.text
    return response.json()["document_id"]


def pdf_of(tenant, document_id: str) -> pymupdf.Document:
    response = tenant.get(f"/api/v1/documents/{document_id}/file")
    assert response.status_code == 200
    return pymupdf.open(stream=response.content, filetype="pdf")


def page_texts(tenant, document_id: str) -> list[str]:
    with pdf_of(tenant, document_id) as doc:
        return [page.get_text().strip() for page in doc]


def test_photo_upload_becomes_a_searchable_pdf(api):
    # A "photo" of a page: render a PDF page to PNG, as a phone camera would capture it.
    with pymupdf.open(stream=make_pdf(["Delivery challan 7781 for Patel Fabrics"], fontsize=14), filetype="pdf") as d:
        png = d[0].get_pixmap(dpi=150).tobytes("png")
    response = upload(api, png, "IMG_2041.png", "image/png")
    assert response.status_code == 202, response.text
    document_id = response.json()["document_id"]

    detail = api.get(f"/api/v1/documents/{document_id}").json()
    assert detail["filename"] == "IMG_2041.pdf" and detail["mime_type"] == "application/pdf"
    assert detail["origin"] == {"operation": "photo", "converted_from": "IMG_2041.png"}
    assert detail["status"] == "completed"  # OCR read it
    results = api.post(f"/api/v1/workspaces/{api.workspace_id}/search", json={"query": "delivery challan"}).json()
    assert results["results"][0]["document_id"] == document_id


def test_spoofed_photo_is_rejected(api):
    assert upload(api, b"just text", "invoice.jpg", "image/jpeg").status_code == 415


def test_merge_keeps_order_and_leaves_originals_untouched(api):
    first, second = make_pdf(["First doc"]), make_pdf(["Second A", "Second B"])
    a, b = upload_id(api, first, "a.pdf"), upload_id(api, second, "b.pdf")

    response = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents/merge",
        json={"document_ids": [b, a], "filename": "../../etc/combined"},
    )
    assert response.status_code == 202, response.text
    merged = response.json()
    assert merged["filename"] == "combined.pdf"  # path parts stripped, .pdf added
    assert page_texts(api, merged["document_id"]) == ["Second A", "Second B", "First doc"]

    detail = api.get(f"/api/v1/documents/{merged['document_id']}").json()
    assert detail["origin"]["operation"] == "merge"
    assert [s["filename"] for s in detail["origin"]["sources"]] == ["b.pdf", "a.pdf"]
    assert detail["status"] == "completed"
    for doc_id, original in ((a, first), (b, second)):
        assert api.get(f"/api/v1/documents/{doc_id}").json()["checksum"] == hashlib.sha256(original).hexdigest()
    audit = api.get(f"/api/v1/organizations/{api.org_id}/audit-logs", params={"action": "document.merge"}).json()
    assert audit[0]["details"]["sources"] == ["b.pdf", "a.pdf"]


def test_merge_validation(api, make_tenant):
    pdf = upload_id(api, make_pdf(["x"]), "x.pdf")
    md = upload(api, b"# notes", "notes.md", "text/markdown").json()["document_id"]
    other = make_tenant("other")
    foreign = upload_id(other, make_pdf(["secret"]), "secret.pdf")
    url = f"/api/v1/workspaces/{api.workspace_id}/documents/merge"

    assert api.post(url, json={"document_ids": [pdf]}).status_code == 422  # needs two
    assert api.post(url, json={"document_ids": [pdf, pdf]}).status_code == 422  # duplicates
    assert api.post(url, json={"document_ids": [pdf, md]}).status_code == 422  # not a PDF
    assert api.post(url, json={"document_ids": [pdf, foreign]}).status_code == 404  # other tenant's document
    assert other.post(url, json={"document_ids": [foreign, foreign]}).status_code == 404  # other tenant's workspace


def test_vendor_pdf_with_two_invoices_is_split_and_each_extracts_correctly(api):
    (pdf1, truth1), (pdf2, truth2) = make_invoice_pdf(1), make_invoice_pdf(2)
    combined = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents/merge",
        json={"document_ids": [upload_id(api, pdf1, "i1.pdf"), upload_id(api, pdf2, "i2.pdf")], "filename": "vendor"},
    ).json()["document_id"]

    parts = api.post(f"/api/v1/documents/{combined}/split", json={}).json()
    assert [p["filename"] for p in parts] == ["vendor - part 1 (p1).pdf", "vendor - part 2 (p2).pdf"]
    for part, truth in zip(parts, (truth1, truth2), strict=True):
        values = extract(api, part["document_id"])["values"]
        assert values["invoice_number"] == truth["invoice_number"]
        assert values["vendor_gstin"] == truth["vendor_gstin"]


def test_split_by_ranges_and_extract_pages(api):
    doc = upload_id(api, make_pdf(["P1", "P2", "P3", "P4"]), "four.pdf")
    parts = api.post(f"/api/v1/documents/{doc}/split", json={"ranges": ["1-2", "4"]}).json()
    assert [page_texts(api, p["document_id"]) for p in parts] == [["P1", "P2"], ["P4"]]

    kept = api.post(f"/api/v1/documents/{doc}/extract-pages", json={"pages": "3, 1"}).json()
    assert kept["filename"] == "four (pages 3,1).pdf"
    assert page_texts(api, kept["document_id"]) == ["P3", "P1"]

    assert api.post(f"/api/v1/documents/{doc}/split", json={"ranges": ["1-4"]}).status_code == 422  # one part
    assert api.post(f"/api/v1/documents/{doc}/extract-pages", json={"pages": "9"}).status_code == 422


def test_rotate_creates_a_rotated_copy(api):
    doc = upload_id(api, make_pdf(["P1", "P2"]), "scan.pdf")
    rotated = api.post(f"/api/v1/documents/{doc}/rotate", json={"pages": "2", "degrees": 90}).json()
    with pdf_of(api, rotated["document_id"]) as pdf:
        assert [p.rotation for p in pdf] == [0, 90]
    with pdf_of(api, doc) as original:
        assert [p.rotation for p in original] == [0, 0]
    assert api.post(f"/api/v1/documents/{doc}/rotate", json={"degrees": 45}).status_code == 422


def test_page_count_and_thumbnails(api, make_tenant):
    doc = upload_id(api, make_pdf(["P1", "P2", "P3"]), "three.pdf")
    assert api.get(f"/api/v1/documents/{doc}/pages").json() == {"document_id": doc, "page_count": 3}
    thumb = api.get(f"/api/v1/documents/{doc}/pages/2/thumbnail", params={"width": 120})
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/png"
    assert thumb.content.startswith(b"\x89PNG")
    assert api.get(f"/api/v1/documents/{doc}/pages/9/thumbnail").status_code == 422

    other = make_tenant("other")
    for request in (
        other.get(f"/api/v1/documents/{doc}/pages"),
        other.get(f"/api/v1/documents/{doc}/pages/1/thumbnail"),
        other.post(f"/api/v1/documents/{doc}/split", json={}),
        other.post(f"/api/v1/documents/{doc}/rotate", json={}),
        other.post(f"/api/v1/documents/{doc}/extract-pages", json={"pages": "1"}),
    ):
        assert request.status_code == 404
