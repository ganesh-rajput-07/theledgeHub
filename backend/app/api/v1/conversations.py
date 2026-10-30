from fastapi import APIRouter, HTTPException, status

from app.api.deps import ConversationDep, DbSession, MessageDep
from app.api.errors import llm_http_error
from app.api.v1.workspaces import ensure_documents_in_workspace
from app.llm.base import LLMError
from app.models import Message, MessageCitation
from app.rag.pipeline import RagAnswer
from app.schemas.chat import (
    AnswerResponse,
    AskRequest,
    CitationRead,
    ConversationRead,
    MessageRead,
    Usage,
)
from app.services.chat_service import ConversationNotReadyError, ask

router = APIRouter(tags=["chat"])


def _citation(citation: MessageCitation) -> CitationRead:
    chunk = citation.chunk
    return CitationRead(
        citation_id=citation.citation_index,
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        filename=chunk.document.filename,
        page_number=chunk.page_number,
        quoted_text=citation.quoted_text,
        score=citation.score,
    )


def _message(message: Message) -> MessageRead:
    is_answer = message.role == "assistant"
    return MessageRead(
        message_id=message.id,
        role=message.role,
        content=message.content,
        status=message.status,
        grounded=bool(message.citations) if is_answer else None,
        citations=[_citation(c) for c in message.citations],
        model=message.model,
        usage=Usage(input_tokens=message.input_tokens, output_tokens=message.output_tokens) if is_answer else None,
        latency_ms=message.latency_ms,
        search_query=message.search_query,
        created_at=message.created_at,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation: ConversationDep):
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation: ConversationDep, db: DbSession):
    db.delete(conversation)
    db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=AnswerResponse)
def ask_question(conversation: ConversationDep, request: AskRequest, db: DbSession):
    ensure_documents_in_workspace(db, conversation.workspace_id, request.document_ids or [])
    try:
        message, result = ask(db, conversation, request.question.strip(), request.document_ids)
    except ConversationNotReadyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LLMError as exc:
        db.rollback()
        raise llm_http_error(exc) from exc
    return _answer(message, result)


def _answer(message: Message, result: RagAnswer) -> AnswerResponse:
    return AnswerResponse(
        message_id=message.id,
        answer=result.answer,
        status=result.status,
        grounded=result.grounded,
        citations=[_citation(c) for c in message.citations],
        model=message.model,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        latency_ms=result.latency_ms,
        truncated=result.truncated,
        search_query=result.search_query,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation: ConversationDep):
    return [_message(m) for m in conversation.messages]


@router.get("/messages/{message_id}/citations", response_model=list[CitationRead])
def get_citations(message: MessageDep):
    return [_citation(c) for c in message.citations]
