from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    truncated: bool = False


class LLMError(Exception):
    """Base for provider failures; the API maps subclasses to HTTP status codes."""


class LLMAuthError(LLMError):
    """The customer's key was rejected or lacks permission."""


class LLMRateLimitError(LLMError):
    """The customer's provider account is rate limited or out of quota."""


class LLMModelNotFoundError(LLMError):
    """The model does not exist or this key cannot use it."""


class LLMRefusalError(LLMError):
    """The model declined to answer."""


class LLMProviderError(LLMError):
    """Any other provider or network failure."""


class LLMUnavailableError(LLMProviderError):
    """The provider is overloaded or temporarily down (HTTP 503 / Anthropic 529). Retrying later, or
    switching to another model, usually helps; nothing is wrong with the request or the key."""


class LLMProvider(Protocol):
    """Every provider adapter implements this; nothing outside app/llm imports a vendor SDK."""

    name: str

    def list_models(self) -> list[str]:
        """Cheap authenticated call, used to validate a key and the chosen model."""
        ...

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse: ...
