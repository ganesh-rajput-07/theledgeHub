import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.base import ChatMessage
from app.llm.factory import build_provider_for_credential
from app.models import Conversation, Message, MessageCitation
from app.rag.pipeline import RagAnswer, answer_question


class ConversationNotReadyError(Exception):
    pass


def _history(db: Session, conversation: Conversation) -> list[ChatMessage]:
    limit = get_settings().chat_history_messages
    recent = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()
    history = [ChatMessage(role=m.role, content=m.content) for m in reversed(recent)]
    # Providers require the history to start with a user turn.
    while history and history[0].role != "user":
        history.pop(0)
    return history


def ask(
    db: Session, conversation: Conversation, question: str, document_ids: list[uuid.UUID] | None
) -> tuple[Message, RagAnswer]:
    credential = conversation.provider_credential
    if credential is None:
        raise ConversationNotReadyError("This conversation's provider was deleted; start a new conversation")
    if not credential.is_active:
        raise ConversationNotReadyError(f"Provider '{credential.label}' is disabled")

    history = _history(db, conversation)
    scope = document_ids if document_ids is not None else conversation.document_ids
    result = answer_question(
        db,
        build_provider_for_credential(credential),
        conversation.model,
        question,
        history,
        conversation.workspace_id,
        scope or None,
    )

    # Persist only after a successful answer, so a provider failure leaves no half-written turn.
    db.add(Message(conversation_id=conversation.id, role="user", content=question))
    db.flush()
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        status=result.status,
        provider=credential.provider,
        model=result.model or conversation.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        search_query=result.search_query,
    )
    db.add(assistant)
    db.flush()
    db.add_all(
        MessageCitation(
            message_id=assistant.id,
            chunk_id=c.chunk.chunk_id,
            citation_index=c.citation_index,
            quoted_text=c.chunk.content,
            score=c.chunk.score,
        )
        for c in result.citations
    )
    if conversation.title is None:
        conversation.title = question[:80]
    db.commit()
    return assistant, result
