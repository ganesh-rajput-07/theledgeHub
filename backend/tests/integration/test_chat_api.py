import pytest
from sqlalchemy import select

from app.database.session import SessionLocal
from app.llm import factory
from app.llm.base import LLMAuthError, LLMRateLimitError, LLMResponse
from app.models import ProviderCredential
from app.rag.query_rewriter import REWRITE_SYSTEM_PROMPT
from tests.factories import make_pdf

FINANCE = [
    "Chapter 1: Company Overview. Our company was established in 2015 and provides software consulting.",
    "Chapter 2: Financials. In fiscal year 2025 total revenue reached INR 190 crore, up 14% from 2024.",
]
HR_POLICY = [
    "Leave Policy. Every employee is entitled to 20 days of paid leave per calendar year.",
    "Insurance. The company provides group health insurance for employees and their dependents.",
]


class FakeProvider:
    """Stands in for a real vendor so tests never call the network."""

    name = "openai"

    def __init__(self, models=("gpt-test",), error=None, text="Revenue reached INR 190 crore [1]. Also [7]."):
        self.models, self.error, self.text, self.calls = list(models), error, text, []
        self.rewrites, self.rewrite_text, self.rewrite_error = [], None, None

    def list_models(self):
        if self.error:
            raise self.error
        return self.models

    def generate(self, system, messages, model, max_tokens):
        if system == REWRITE_SYSTEM_PROMPT:
            self.rewrites.append(messages[0].content)
            if self.rewrite_error:
                raise self.rewrite_error
            return LLMResponse(text=self.rewrite_text or "", model=model, input_tokens=40, output_tokens=6)
        self.calls.append(messages)
        if self.error:
            raise self.error
        return LLMResponse(text=self.text, model=model, input_tokens=300, output_tokens=12)


@pytest.fixture
def fake(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(factory, "build_provider", lambda *a, **k: provider)
    return provider


def upload(api, filename, pages):
    response = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents",
        files={"file": (filename, make_pdf(pages), "application/pdf")},
    )
    return response.json()["document_id"]


def mock_conversation(api, document_ids):
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "mock", "label": "Mock", "default_model": "mock-1"},
    ).json()
    return api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": document_ids},
    ).json()


def ask(api, conversation_id, question, **body):
    return api.post(f"/api/v1/conversations/{conversation_id}/messages", json={"question": question, **body})


# ---------------------------------------------------------------- providers (BYOK)


def test_byok_key_is_validated_encrypted_and_never_returned(api, fake):
    response = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "Team key", "api_key": "sk-live-SECRET-9876", "default_model": "gpt-test"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["key_hint"] == "…9876"
    assert "SECRET" not in response.text and "api_key" not in body

    with SessionLocal() as db:
        stored = db.scalar(select(ProviderCredential).where(ProviderCredential.id == body["id"]))
    assert stored.encrypted_api_key and "SECRET" not in stored.encrypted_api_key

    listed = api.get(f"/api/v1/organizations/{api.org_id}/providers").text
    assert "SECRET" not in listed


def test_rejected_key_is_not_stored(api, fake):
    fake.error = LLMAuthError("OpenAI rejected the API key")
    before = len(api.get(f"/api/v1/organizations/{api.org_id}/providers").json())
    response = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "Bad", "api_key": "sk-wrong-0000", "default_model": "gpt-test"},
    )
    assert response.status_code == 400
    assert "rejected" in response.json()["detail"]
    assert len(api.get(f"/api/v1/organizations/{api.org_id}/providers").json()) == before


def test_unknown_model_and_missing_key_are_rejected(api, fake):
    response = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "x", "api_key": "sk-1234567890", "default_model": "gpt-nope"},
    )
    assert response.status_code == 400 and "not available" in response.json()["detail"]

    response = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "anthropic", "label": "x", "default_model": "m"},
    )
    assert response.status_code == 400 and "requires an api_key" in response.json()["detail"]


def test_rotate_key_and_delete_provider(api, fake):
    created = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-old-key-1111", "default_model": "gpt-test"},
    ).json()
    rotated = api.patch(f"/api/v1/providers/{created['id']}", json={"api_key": "sk-new-key-2222"}).json()
    assert rotated["key_hint"] == "…2222"
    assert api.delete(f"/api/v1/providers/{created['id']}").status_code == 204
    assert api.get(f"/api/v1/providers/{created['id']}").status_code == 404


# ---------------------------------------------------------------- chat + citations


def test_answer_has_citations_pointing_at_retrieved_pages(api):
    finance = upload(api, "finance-chat.pdf", FINANCE)
    hr = upload(api, "hr-chat.pdf", HR_POLICY)
    conversation = mock_conversation(api, [finance, hr])

    response = ask(api, conversation["id"], "How many days of paid leave do employees get?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed" and body["grounded"] is True
    assert "20 days of paid leave" in body["answer"]

    citation = body["citations"][0]
    assert (citation["citation_id"], citation["filename"], citation["page_number"]) == (1, "hr-chat.pdf", 1)
    assert citation["document_id"] == hr
    assert "20 days of paid leave" in citation["quoted_text"]
    assert body["usage"]["input_tokens"] > 0

    stored = api.get(f"/api/v1/messages/{body['message_id']}/citations").json()
    assert stored == body["citations"]


def test_irrelevant_question_returns_not_found_without_calling_llm(api, fake, monkeypatch):
    finance = upload(api, "finance-nf.pdf", FINANCE)
    fake.models = ["gpt-test"]
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-3333", "default_model": "gpt-test"},
    ).json()
    conversation = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": [finance]},
    ).json()

    body = ask(api, conversation["id"], "What is the recipe for chocolate cake?").json()
    assert body["status"] == "not_found" and body["grounded"] is False and body["citations"] == []
    assert fake.calls == []  # the customer's tokens were not spent


def test_hallucinated_citation_is_stripped(api, fake):
    finance = upload(api, "finance-hall.pdf", FINANCE)
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-4444", "default_model": "gpt-test"},
    ).json()
    conversation = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": [finance]},
    ).json()

    body = ask(api, conversation["id"], "What was total revenue in fiscal year 2025?").json()
    assert body["answer"] == "Revenue reached INR 190 crore [1]. Also."
    assert [c["citation_id"] for c in body["citations"]] == [1]
    # The prompt really contained the retrieved sources and the question.
    prompt = fake.calls[0][-1].content
    assert '<source id="1" document="finance-hall.pdf" page="2">' in prompt
    assert prompt.endswith("Question: What was total revenue in fiscal year 2025?")


def test_llm_not_found_token_becomes_not_found(api, fake):
    fake.text = "NOT_FOUND"
    finance = upload(api, "finance-tok.pdf", FINANCE)
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-5555", "default_model": "gpt-test"},
    ).json()
    conversation = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": [finance]},
    ).json()
    body = ask(api, conversation["id"], "What was the revenue growth in 2025?").json()
    assert body["status"] == "not_found"
    assert body["answer"] == "I couldn't find information about this in the selected documents."


def test_history_is_sent_and_stored_in_order(api, fake):
    finance = upload(api, "finance-hist.pdf", FINANCE)
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-6666", "default_model": "gpt-test"},
    ).json()
    conversation = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": [finance]},
    ).json()

    ask(api, conversation["id"], "What was total revenue in 2025?")
    ask(api, conversation["id"], "And how much did revenue grow compared with 2024?")

    second_prompt = fake.calls[1]
    assert [m.role for m in second_prompt] == ["user", "assistant", "user"]
    assert second_prompt[0].content == "What was total revenue in 2025?"  # history without sources

    messages = api.get(f"/api/v1/conversations/{conversation['id']}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["grounded"] is True and messages[1]["citations"]
    assert api.get(f"/api/v1/conversations/{conversation['id']}").json()["title"] == "What was total revenue in 2025?"


def test_provider_errors_map_to_http_and_leave_no_messages(api, fake):
    finance = upload(api, "finance-err.pdf", FINANCE)
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-7777", "default_model": "gpt-test"},
    ).json()
    conversation = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": [finance]},
    ).json()

    fake.error = LLMRateLimitError("OpenAI rate limit or quota exceeded")
    assert ask(api, conversation["id"], "What was revenue in 2025?").status_code == 429
    fake.error = LLMAuthError("OpenAI rejected the API key")
    assert ask(api, conversation["id"], "What was revenue in 2025?").status_code == 400
    assert api.get(f"/api/v1/conversations/{conversation['id']}/messages").json() == []


def test_deleted_provider_blocks_new_questions_but_keeps_history(api):
    finance = upload(api, "finance-del.pdf", FINANCE)
    conversation = mock_conversation(api, [finance])
    ask(api, conversation["id"], "What was revenue in 2025?")

    api.delete(f"/api/v1/providers/{conversation['provider_credential_id']}")
    assert ask(api, conversation["id"], "Another question?").status_code == 409
    assert len(api.get(f"/api/v1/conversations/{conversation['id']}/messages").json()) == 2


def test_deleting_document_removes_its_citations(api):
    hr = upload(api, "hr-cascade.pdf", HR_POLICY)
    conversation = mock_conversation(api, [hr])
    message_id = ask(api, conversation["id"], "How many days of paid leave?").json()["message_id"]
    assert api.get(f"/api/v1/messages/{message_id}/citations").json()

    api.delete(f"/api/v1/documents/{hr}")
    assert api.get(f"/api/v1/messages/{message_id}/citations").json() == []


def test_validation_errors(api):
    assert (
        api.post(
            f"/api/v1/workspaces/{api.workspace_id}/conversations",
            json={"provider_id": "00000000-0000-0000-0000-000000000000"},
        ).status_code
        == 404
    )
    conversation = mock_conversation(api, [])
    assert ask(api, conversation["id"], "").status_code == 422
    assert (
        api.post(
            f"/api/v1/organizations/{api.org_id}/providers",
            json={"provider": "nope", "label": "x", "default_model": "m"},
        ).status_code
        == 422
    )


# ---------------------------------------------------------------- follow-up questions


def openai_conversation(api, document_ids):
    provider = api.post(
        f"/api/v1/organizations/{api.org_id}/providers",
        json={"provider": "openai", "label": "k", "api_key": "sk-test-key-8888", "default_model": "gpt-test"},
    ).json()
    return api.post(
        f"/api/v1/workspaces/{api.workspace_id}/conversations",
        json={"provider_id": provider["id"], "document_ids": document_ids},
    ).json()


def test_follow_up_is_rewritten_before_search(api, fake):
    finance = upload(api, "finance-follow.pdf", FINANCE)
    hr = upload(api, "hr-follow.pdf", HR_POLICY)
    conversation = openai_conversation(api, [finance, hr])

    first = ask(api, conversation["id"], "How many days of paid leave do employees get?").json()
    assert first["search_query"] == "How many days of paid leave do employees get?"
    assert fake.rewrites == []  # nothing to resolve on the first question

    fake.rewrite_text = "Does the company provide health insurance for employees' dependents?"
    body = ask(api, conversation["id"], "And their families?").json()

    assert "<conversation>" in fake.rewrites[0] and "Latest message: And their families?" in fake.rewrites[0]
    assert body["search_query"] == fake.rewrite_text
    assert body["citations"][0]["filename"] == "hr-follow.pdf" and body["citations"][0]["page_number"] == 2
    # The answer prompt keeps the user's own wording; only search used the rewrite.
    assert fake.calls[-1][-1].content.endswith("Question: And their families?")
    # Usage includes the rewrite call (40 in / 6 out) on top of the answer (300 / 12).
    assert body["usage"] == {"input_tokens": 340, "output_tokens": 18}

    stored = api.get(f"/api/v1/conversations/{conversation['id']}/messages").json()
    assert stored[-1]["search_query"] == fake.rewrite_text


def test_vague_follow_up_without_rewrite_would_miss(api, fake, monkeypatch):
    """Why this exists: on its own, a follow-up like this finds nothing relevant."""
    from app.core.config import get_settings

    finance = upload(api, "finance-miss.pdf", FINANCE)
    conversation = openai_conversation(api, [finance])
    ask(api, conversation["id"], "What was total revenue in fiscal year 2025?")

    monkeypatch.setattr(get_settings(), "query_rewrite", "off")
    assert ask(api, conversation["id"], "And what about the year before?").json()["status"] == "not_found"

    monkeypatch.setattr(get_settings(), "query_rewrite", "llm")
    fake.rewrite_text = "What was total revenue in fiscal year 2024?"
    body = ask(api, conversation["id"], "And what about the year before?").json()
    assert body["status"] == "completed" and body["citations"][0]["page_number"] == 2


def test_failed_rewrite_falls_back_to_previous_question(api, fake):
    finance = upload(api, "finance-fallback.pdf", FINANCE)
    conversation = openai_conversation(api, [finance])
    ask(api, conversation["id"], "What was total revenue in fiscal year 2025?")

    fake.rewrite_error = LLMRateLimitError("slow down")
    body = ask(api, conversation["id"], "And the growth?").json()
    assert body["status"] == "completed"
    assert body["search_query"] == "What was total revenue in fiscal year 2025? And the growth?"
