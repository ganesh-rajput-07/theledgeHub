from google import genai
from google.genai import errors, types

from app.llm.base import (
    ChatMessage,
    LLMAuthError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMUnavailableError,
)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, timeout: float):
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000),
                # The SDK doesn't retry by default; match the OpenAI/Anthropic clients (3 attempts in total)
                # so short overload spikes (429/503) are ridden out.
                retry_options=types.HttpRetryOptions(attempts=3, initial_delay=1.0, max_delay=8.0),
            ),
        )

    def list_models(self) -> list[str]:
        with _translate_errors():
            return [model.name.removeprefix("models/") for model in self._client.models.list()]

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse:
        contents = [
            types.Content(role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)])
            for m in messages
        ]
        with _translate_errors():
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
            )
        usage = response.usage_metadata
        finish = response.candidates[0].finish_reason if response.candidates else None
        return LLMResponse(
            text=response.text or "",
            model=model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            truncated=finish == types.FinishReason.MAX_TOKENS,
        )


class _translate_errors:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False
        if isinstance(exc, errors.ClientError):
            # Gemini reports a bad key as 400 API_KEY_INVALID rather than 401.
            if exc.code in (401, 403) or "API key" in str(exc):
                raise LLMAuthError("Gemini rejected the API key") from exc
            if exc.code == 429:
                raise LLMRateLimitError("Gemini rate limit or quota exceeded") from exc
            if exc.code == 404:
                raise LLMModelNotFoundError("Model not found for this Gemini key") from exc
            raise LLMProviderError(f"Gemini error {exc.code}: {exc.message}") from exc
        if isinstance(exc, errors.ServerError) and exc.code == 503:
            raise LLMUnavailableError(
                "Gemini is overloaded right now (503). Try again in a minute, or switch to another model."
            ) from exc
        if isinstance(exc, errors.APIError):
            raise LLMProviderError(f"Gemini error {exc.code}: {exc.message}") from exc
        return False
