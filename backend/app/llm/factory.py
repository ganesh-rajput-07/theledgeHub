from enum import StrEnum

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.llm.base import LLMProvider


class ProviderName(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    MOCK = "mock"


# Providers that need a customer API key (BYOK). Ollama needs a base URL instead.
KEYED_PROVIDERS = {ProviderName.OPENAI, ProviderName.ANTHROPIC, ProviderName.GEMINI}


def build_provider(provider: str, api_key: str | None = None, base_url: str | None = None) -> LLMProvider:
    settings = get_settings()
    match ProviderName(provider):
        case ProviderName.OPENAI:
            from app.llm.openai_provider import OpenAIProvider

            return OpenAIProvider(api_key or "", timeout=settings.llm_timeout_seconds)
        case ProviderName.ANTHROPIC:
            from app.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider(api_key or "", timeout=settings.llm_timeout_seconds)
        case ProviderName.GEMINI:
            from app.llm.gemini_provider import GeminiProvider

            return GeminiProvider(api_key or "", timeout=settings.llm_timeout_seconds)
        case ProviderName.OLLAMA:
            from app.llm.ollama_provider import OllamaProvider

            return OllamaProvider(base_url or settings.ollama_base_url, timeout=settings.ollama_timeout_seconds)
        case ProviderName.MOCK:
            from app.llm.mock_provider import MockProvider

            return MockProvider()


def build_provider_for_credential(credential) -> LLMProvider:
    api_key = decrypt_secret(credential.encrypted_api_key) if credential.encrypted_api_key else None
    return build_provider(credential.provider, api_key=api_key, base_url=credential.base_url)
