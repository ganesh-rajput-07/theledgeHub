from dataclasses import dataclass

from app.llm.base import ChatMessage, LLMAuthError, LLMProvider, LLMRateLimitError, LLMUnavailableError

REWRITE_SYSTEM_PROMPT = """You turn the user's latest message into a standalone search query for a \
document search engine. Use the conversation only to resolve references such as "it", "that year", \
"the previous one" or "what about X?". Keep names, numbers, dates and key terms. If the latest message \
is already self-contained, return it unchanged. Reply with the query only - no explanation, no quotes."""

MAX_QUERY_CHARS = 500


@dataclass(frozen=True)
class RewrittenQuery:
    query: str
    method: str  # none | llm | concat
    input_tokens: int = 0
    output_tokens: int = 0


def _render(history: list[ChatMessage], question: str) -> str:
    turns = "\n".join(f"{m.role}: {m.content}" for m in history)
    return f"<conversation>\n{turns}\n</conversation>\n\nLatest message: {question}"


def _concat_fallback(history: list[ChatMessage], question: str) -> str:
    """Cheap, provider-free fallback: the previous question usually carries the missing subject."""
    previous = next((m.content for m in reversed(history) if m.role == "user"), "")
    return f"{previous} {question}".strip()[:MAX_QUERY_CHARS]


def rewrite_query(
    llm: LLMProvider, model: str, question: str, history: list[ChatMessage], mode: str, max_tokens: int
) -> RewrittenQuery:
    """Make a follow-up question searchable on its own. Only the retrieval step uses the result;
    the answer prompt still gets the user's original wording plus history."""
    if not history or mode == "off":
        return RewrittenQuery(question, "none")
    if mode == "concat":
        return RewrittenQuery(_concat_fallback(history, question), "concat")

    try:
        response = llm.generate(
            REWRITE_SYSTEM_PROMPT, [ChatMessage("user", _render(history, question))], model, max_tokens
        )
    except (LLMAuthError, LLMRateLimitError, LLMUnavailableError):
        # The answer call would hit the same wall: fail now instead of making the user wait twice.
        raise
    except Exception:  # noqa: BLE001 - any other rewrite failure must never block the answer
        return RewrittenQuery(_concat_fallback(history, question), "concat")

    query = response.text.strip().strip('"').strip()
    if not query or response.truncated or len(query) > MAX_QUERY_CHARS:
        return RewrittenQuery(_concat_fallback(history, question), "concat")
    return RewrittenQuery(query, "llm", response.input_tokens or 0, response.output_tokens or 0)
