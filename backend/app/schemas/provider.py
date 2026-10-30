import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.llm.factory import ProviderName


class ProviderCreate(BaseModel):
    provider: ProviderName
    label: str = Field(min_length=1, max_length=100)
    # SecretStr keeps the key out of logs, reprs and error messages.
    api_key: SecretStr | None = None
    base_url: str | None = Field(default=None, max_length=500)
    default_model: str = Field(min_length=1, max_length=200)


class ProviderUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: SecretStr | None = None
    base_url: str | None = Field(default=None, max_length=500)
    default_model: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class ProviderRead(BaseModel):
    """Never contains the key itself - only a hint like '…a1b2'."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    label: str
    key_hint: str | None
    base_url: str | None
    default_model: str
    is_active: bool
    last_validated_at: datetime | None
    created_at: datetime


class ProviderModels(BaseModel):
    provider_id: uuid.UUID
    models: list[str]
