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
    retrieval_mode: str = "hybrid"  # hybrid (vector + full-text, rank fusion) | vector
    hybrid_keyword_weight: float = 0.5  # weight of the full-text ranking in rank fusion (vector = 1.0)
    # A cross-encoder re-scores the best candidates; measured +7 points top-1 accuracy (docs/evaluation.md).
    rerank_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    rerank_candidates: int = 20

    # OCR for scanned / image-only PDF pages (RapidOCR, CPU, no system packages needed).
    ocr_enabled: bool = True
    ocr_dpi: int = 200
    ocr_min_text_chars: int = 20  # pages with less extracted text than this get OCR'd
    ocr_max_side_len: int = 1280  # detection input size; lower = faster, higher = better on small print

    # Answer generation (BYOK)
    llm_max_tokens: int = 16000  # reasoning models spend part of this on thinking; don't lowball it
    llm_timeout_seconds: float = 120.0
    ollama_timeout_seconds: float = 600.0  # local CPU models are slow
    ollama_base_url: str = "http://localhost:11434"  # used when a provider connection sets no base_url
    # Below this, retrieval found nothing relevant and the LLM is not called. 0.30 from the evaluation
    # (docs/evaluation.md): it refuses some unanswerable questions without losing any answerable one.
    rag_min_score: float = 0.30
    chat_history_messages: int = 6
    # Follow-up questions are rewritten into standalone search queries: llm | concat | off
    query_rewrite: str = "llm"
    query_rewrite_max_tokens: int = 2048

    # Document processing: "queue" = separate worker processes (python -m app.worker), safe with many API
    # workers; "inline" = run in the API process right after the upload response (single process / tests).
    ingestion_mode: str = "inline"
    worker_poll_seconds: float = 1.0
    job_stale_seconds: int = 1800  # a job "processing" longer than this lost its worker and is requeued
    job_max_attempts: int = 3

    # Brute-force protection (per process; use a shared store such as Redis when running several workers)
    login_max_failures: int = 5  # per account per window
    login_ip_max_attempts: int = 30  # per client IP per window
    register_ip_max_attempts: int = 10
    rate_limit_window_seconds: int = 900
    # Only these addresses may tell us the real client IP via X-Forwarded-For (e.g. the Next.js server).
    trusted_proxies: str = "127.0.0.1/32,::1/128"

    storage_dir: str = "storage"
    max_upload_mb: int = 25

    @property
    def allow_mock_provider(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
