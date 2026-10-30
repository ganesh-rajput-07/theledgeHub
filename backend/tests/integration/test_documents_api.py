from pathlib import Path

from app.core.config import get_settings
from tests.factories import make_pdf

LONG_PAGE = " ".join(f"Revenue grew by {i} percent in quarter {i}." for i in range(1, 70))


def upload(api, filename: str, data: bytes, content_type: str = "application/pdf"):
    return api.post(f"/api/v1/workspaces/{api.workspace_id}/documents", files={"file": (filename, data, content_type)})


def test_upload_pdf_and_inspect_chunks(api):
    pdf = make_pdf(["Chapter 1: Company Overview. Our company was established in 2015.", LONG_PAGE])
    response = upload(api, "annual-report.pdf", pdf)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    document_id = body["document_id"]

    # TestClient runs background tasks before returning, so ingestion has finished here.
    status = api.get(f"/api/v1/documents/{document_id}/status").json()
    assert status["status"] == "completed", status
    assert status["chunk_count"] >= 3

    detail = api.get(f"/api/v1/documents/{document_id}").json()
    assert detail["page_count"] == 2
    assert detail["filename"] == "annual-report.pdf"
    assert len(detail["checksum"]) == 64

    chunks = api.get(f"/api/v1/documents/{document_id}/chunks", params={"limit": 200}).json()
    assert chunks["total"] == status["chunk_count"]
    first = chunks["items"][0]
    assert first["page_number"] == 1
    assert "established in 2015" in first["content"]
    assert {c["page_number"] for c in chunks["items"]} == {1, 2}
    assert all(c["token_count"] <= get_settings().chunk_size for c in chunks["items"])

    listed = api.get(f"/api/v1/workspaces/{api.workspace_id}/documents").json()
    assert document_id in {d["id"] for d in listed}


def test_text_only_markdown_upload(api):
    response = upload(api, "notes.md", b"# Leave policy\n\nEmployees get 20 days of leave.", "text/markdown")
    document_id = response.json()["document_id"]
    chunks = api.get(f"/api/v1/documents/{document_id}/chunks").json()["items"]
    assert chunks[0]["page_number"] is None
    assert "20 days of leave" in chunks[0]["content"]


def test_pdf_without_text_is_marked_failed(api):
    document_id = upload(api, "scanned.pdf", make_pdf([""])).json()["document_id"]
    status = api.get(f"/api/v1/documents/{document_id}/status").json()
    assert status["status"] == "failed"
    assert "No extractable text" in status["error_message"]


def test_rejects_spoofed_pdf(api):
    response = upload(api, "invoice.pdf", b"<script>not a pdf</script>")
    assert response.status_code == 415


def test_reprocess_replaces_chunks(api):
    document_id = upload(api, "r.pdf", make_pdf([LONG_PAGE])).json()["document_id"]
    before = api.get(f"/api/v1/documents/{document_id}/chunks").json()
    assert api.post(f"/api/v1/documents/{document_id}/reprocess").status_code == 202
    after = api.get(f"/api/v1/documents/{document_id}/chunks").json()
    assert after["total"] == before["total"]
    assert {c["id"] for c in after["items"]}.isdisjoint({c["id"] for c in before["items"]})


def test_delete_removes_file_and_chunks(api):
    document_id = upload(api, "d.pdf", make_pdf(["Delete me."])).json()["document_id"]
    stored = list(Path(get_settings().storage_dir).glob(f"{document_id}.*"))
    assert stored

    assert api.delete(f"/api/v1/documents/{document_id}").status_code == 204
    assert api.get(f"/api/v1/documents/{document_id}").status_code == 404
    assert api.get(f"/api/v1/documents/{document_id}/chunks").status_code == 404
    assert not stored[0].exists()


def test_unknown_document_returns_404(api):
    assert api.get("/api/v1/documents/00000000-0000-0000-0000-000000000000").status_code == 404
