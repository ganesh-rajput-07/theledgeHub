from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KnowledgeHub Licensing"
    database_url: str
    cookie_secure: bool = True  # HTTPS-only cookies; set false only for local http
    session_hours: int = 12
    login_max_failures: int = 5  # wrong passwords before the admin account is locked for a while
    login_lock_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
