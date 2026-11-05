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
    lease_private_key_file: str = "keys/lease_private.pem"  # Ed25519; create with: python -m app.cli generate-keys
    public_url: str = "http://localhost:8002"  # shown to customers in messages, e.g. the renewal link
    register_ip_per_hour: int = 10
    app_login_ip_per_15min: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
