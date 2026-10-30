from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KnowledgeHub AI"
    app_env: str = "development"
    debug: bool = False

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    encryption_key: str

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # all-MiniLM-L6-v2 truncates input at 256 tokens, so chunks must stay below that.
    chunk_size: int = 250
    chunk_overlap: int = 50

    retrieval_top_k: int = 8

    # OCR for scanned / image-only PDF pages (RapidOCR, CPU, no system packages needed).
    ocr_enabled: bool = True
    ocr_dpi: int = 200
    ocr_min_text_chars: int = 20  # pages with less extracted text than this get OCR'd
    ocr_max_side_len: int = 1280  # detection input size; lower = faster, higher = better on small print

    # Answer generation (BYOK)
    llm_max_tokens: int = 16000  # reasoning models spend part of this on thinking; don't lowball it
    llm_timeout_seconds: float = 120.0
    ollama_timeout_seconds: float = 600.0  # local CPU models are slow
    rag_min_score: float = 0.25  # below this, retrieval found nothing relevant and the LLM is not called
    chat_history_messages: int = 6
    # Follow-up questions are rewritten into standalone search queries: llm | concat | off
    query_rewrite: str = "llm"
    query_rewrite_max_tokens: int = 2048

    storage_dir: str = "storage"
    max_upload_mb: int = 25

    @property
    def allow_mock_provider(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
