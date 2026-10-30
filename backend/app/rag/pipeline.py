import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMError, LLMProvider, LLMProviderError
from app.rag.citations import Citation, extract_citations
from app.rag.embeddings import get_embedding_provider
from app.rag.prompt_builder import NOT_FOUND_TOKEN, SYSTEM_PROMPT, build_messages
from app.rag.query_rewriter import rewrite_query
from app.rag.retriever import retrieve

NOT_FOUND_ANSWER = "I couldn't find information about this in the selected documents."


@dataclass
class RagAnswer:
    answer: str
    status: str  # completed | not_found
    citations: list[Citation] = field(default_factory=list)
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    truncated: bool = False
    search_query: str = ""
    rewrite_method: str = "none"

    @property
    def grounded(self) -> bool:
        return bool(self.citations)


def answer_question(
    db: Session,
    llm: LLMProvider,
    model: str,
    question: str,
    history: list[ChatMessage],
    workspace_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None,
) -> RagAnswer:
    """rewrite follow-up -> retrieve -> (nothing relevant? NOT_FOUND without calling the LLM)
    -> prompt -> generate -> cite"""
    settings = get_settings()
    started = time.perf_counter()

    rewritten = rewrite_query(llm, model, question, history, settings.query_rewrite, settings.query_rewrite_max_tokens)
    chunks = retrieve(
        db,
        get_embedding_provider(),
        rewritten.query,
        top_k=settings.retrieval_top_k,
        workspace_id=workspace_id,
        document_ids=document_ids,
        min_score=settings.rag_min_score,
    )
    if not chunks:
        # Nothing relevant was retrieved: don't spend the customer's tokens on a guess.
        return RagAnswer(
            answer=NOT_FOUND_ANSWER,
            status="not_found",
            input_tokens=rewritten.input_tokens or None,
            output_tokens=rewritten.output_tokens or None,
            latency_ms=_ms_since(started),
            search_query=rewritten.query,
            rewrite_method=rewritten.method,
        )

    try:
        response = llm.generate(
            SYSTEM_PROMPT, build_messages(question, chunks, history), model, settings.llm_max_tokens
        )
    except LLMError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"{llm.name} request failed: {exc}") from exc

    result = RagAnswer(
        answer="",
        status="completed",
        model=response.model,
        # Usage covers both calls (rewrite + answer): it is the customer's bill.
        input_tokens=(response.input_tokens or 0) + rewritten.input_tokens or None,
        output_tokens=(response.output_tokens or 0) + rewritten.output_tokens or None,
        truncated=response.truncated,
        latency_ms=_ms_since(started),
        search_query=rewritten.query,
        rewrite_method=rewritten.method,
    )
    text = response.text.strip()
    if not text or text.startswith(NOT_FOUND_TOKEN):
        result.answer, result.status = NOT_FOUND_ANSWER, "not_found"
        return result

    result.answer, result.citations = extract_citations(text, chunks)
    return result


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
