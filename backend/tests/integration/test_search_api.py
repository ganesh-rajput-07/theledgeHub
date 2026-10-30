from sqlalchemy import func, select

from app.database.session import SessionLocal
from app.models import DocumentChunk
from tests.factories import make_pdf, make_scanned_pdf

FINANCE = [
    "Chapter 1: Company Overview. Our company was established in 2015 and provides software consulting.",
    "Chapter 2: Financials. In fiscal year 2025 total revenue reached INR 190 crore, up 14% from 2024.",
]
HR_POLICY = [
    "Leave Policy. Every employee is entitled to 20 days of paid leave per calendar year.",
    "Insurance. The company provides group health insurance for employees and their dependents.",
]


def upload(api, filename, data):
    response = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents", files={"file": (filename, data, "application/pdf")}
    )
    assert response.status_code == 202
    return response.json()["document_id"]


def search(api, query, **body):
    response = api.post(f"/api/v1/workspaces/{api.workspace_id}/search", json={"query": query, **body})
    assert response.status_code == 200, response.text
    return response.json()["results"]


def test_ingestion_stores_embeddings(api):
    document_id = upload(api, "finance-embed.pdf", make_pdf(FINANCE))
    detail = api.get(f"/api/v1/documents/{document_id}").json()
    assert detail["status"] == "completed"
    assert detail["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    with SessionLocal() as db:
        missing = db.scalar(
            select(func.count())
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.embedding.is_(None))
        )
    assert missing == 0


def test_search_finds_the_right_document_and_page(api):
    finance_id = upload(api, "finance.pdf", make_pdf(FINANCE))
    hr_id = upload(api, "hr-policy.pdf", make_pdf(HR_POLICY))
    scope = [finance_id, hr_id]

    top = search(api, "How many vacation days do staff get?", document_ids=scope)[0]
    assert (top["document_id"], top["filename"], top["page_number"]) == (hr_id, "hr-policy.pdf", 1)
    assert "20 days of paid leave" in top["content"]

    top = search(api, "What was the revenue last year?", document_ids=scope)[0]
    assert (top["document_id"], top["page_number"]) == (finance_id, 2)

    results = search(api, "health insurance", document_ids=scope, top_k=3)
    assert len(results) == 3
    assert results[0]["page_number"] == 2
    assert [r["score"] for r in results] == sorted((r["score"] for r in results), reverse=True)


def test_search_document_filter_and_min_score(api):
    finance_id = upload(api, "finance-filter.pdf", make_pdf(FINANCE))
    upload(api, "hr-filter.pdf", make_pdf(HR_POLICY))

    results = search(api, "paid leave", document_ids=[finance_id])
    assert results and {r["document_id"] for r in results} == {finance_id}

    assert search(api, "paid leave", document_ids=[finance_id], min_score=0.99) == []


def test_search_validation(api):
    assert api.post(f"/api/v1/workspaces/{api.workspace_id}/search", json={"query": ""}).status_code == 422
    assert (
        api.post(f"/api/v1/workspaces/{api.workspace_id}/search", json={"query": "x", "top_k": 500}).status_code == 422
    )


def test_scanned_pdf_is_ocrd_and_searchable(api):
    document_id = upload(api, "scanned-policy.pdf", make_scanned_pdf(HR_POLICY))
    status = api.get(f"/api/v1/documents/{document_id}/status").json()
    assert status["status"] == "completed", status

    chunks = api.get(f"/api/v1/documents/{document_id}/chunks").json()["items"]
    assert [c["page_number"] for c in chunks] == [1, 2]
    assert all(c["metadata"] == {"ocr": True} for c in chunks)
    assert "20 days of paid leave" in chunks[0]["content"]
    assert "group health insurance for employees" in chunks[1]["content"]

    top = search(api, "Does the company offer health insurance?", document_ids=[document_id])[0]
    assert top["page_number"] == 2
