import anthropic

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

# Models that accept output_config.effort. Opus 5.5 defaults to "medium" - we set it explicitly.
_EFFORT_MODELS = {
    "claude-fable-5-1",
    "claude-fable-5",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5-5",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-haiku-5-5",
}
# Models where a safety-classifier refusal can be retried server-side on another model.
_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, timeout: float, http_client=None):
        kwargs = {"http_client": http_client} if http_client is not None else {}
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2, **kwargs)

    def list_models(self) -> list[str]:
        with _translate_errors():
            return [model.id for model in self._client.models.list()]

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse:
        request = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if model in _EFFORT_MODELS:
            request["output_config"] = {"effort": "medium"}
        with _translate_errors():
            if model in _FALLBACK_MODELS:
                response = self._client.beta.messages.create(
                    **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                response = self._client.messages.create(**request)

        if response.stop_reason == "refusal":
            raise LLMRefusalError("The model declined to answer this question")
        return LLMResponse(
            text="".join(block.text for block in response.content if block.type == "text"),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            truncated=response.stop_reason == "max_tokens",
        )


class _translate_errors:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False
        if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
            raise LLMAuthError("Anthropic rejected the API key") from exc
        if isinstance(exc, anthropic.RateLimitError):
            raise LLMRateLimitError("Anthropic rate limit or quota exceeded") from exc
        if isinstance(exc, anthropic.NotFoundError):
            raise LLMModelNotFoundError("Model not found for this Anthropic key") from exc
        if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (503, 529):
            raise LLMUnavailableError(
                "Anthropic is overloaded right now. Try again in a minute, or switch to another model."
            ) from exc
        if isinstance(exc, anthropic.APIStatusError):
            raise LLMProviderError(f"Anthropic error {exc.status_code}: {exc.message}") from exc
        if isinstance(exc, anthropic.APIConnectionError):
            raise LLMProviderError("Could not reach Anthropic") from exc
        return False
