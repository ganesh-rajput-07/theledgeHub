import openai

from app.llm.base import (
    ChatMessage,
    LLMAuthError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMResponse,
    LLMUnavailableError,
)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, timeout: float, http_client=None):
        kwargs = {"http_client": http_client} if http_client is not None else {}
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=2, **kwargs)

    def list_models(self) -> list[str]:
        with _translate_errors():
            return [model.id for model in self._client.models.list()]

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse:
        with _translate_errors():
            response = self._client.responses.create(
                model=model,
                instructions=system,
                input=[{"role": m.role, "content": m.content} for m in messages],
                max_output_tokens=max_tokens,
                store=False,  # customer documents are in the prompt; don't keep them provider-side
            )
        text = response.output_text
        if not text and _has_refusal(response):
            raise LLMRefusalError("The model declined to answer this question")
        usage = response.usage
        return LLMResponse(
            text=text,
            model=response.model,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            truncated=response.status == "incomplete",
        )


def _has_refusal(response) -> bool:
    return any(
        getattr(part, "type", None) == "refusal"
        for item in response.output or []
        for part in getattr(item, "content", None) or []
    )


class _translate_errors:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False
        if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
            raise LLMAuthError("OpenAI rejected the API key") from exc
        if isinstance(exc, openai.RateLimitError):
            raise LLMRateLimitError("OpenAI rate limit or quota exceeded") from exc
        if isinstance(exc, openai.NotFoundError):
            raise LLMModelNotFoundError("Model not found for this OpenAI key") from exc
        if isinstance(exc, openai.APIStatusError) and exc.status_code == 503:
            raise LLMUnavailableError(
                "OpenAI is overloaded right now. Try again in a minute, or switch to another model."
            ) from exc
        if isinstance(exc, openai.APIStatusError):
            raise LLMProviderError(f"OpenAI error {exc.status_code}: {exc.message}") from exc
        if isinstance(exc, openai.APIConnectionError):
            raise LLMProviderError("Could not reach OpenAI") from exc
        return False
