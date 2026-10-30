import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret, secret_hint
from app.llm import factory
from app.llm.factory import KEYED_PROVIDERS, ProviderName
from app.models import ProviderCredential
from app.schemas.provider import ProviderCreate, ProviderUpdate


class ProviderConfigError(Exception):
    pass


def _check_config(provider: ProviderName, api_key: str | None, base_url: str | None) -> None:
    if provider == ProviderName.MOCK and not get_settings().allow_mock_provider:
        raise ProviderConfigError("The mock provider is disabled in production")
    if provider in KEYED_PROVIDERS and not api_key:
        raise ProviderConfigError(f"{provider} requires an api_key")
    if provider not in KEYED_PROVIDERS and api_key:
        raise ProviderConfigError(f"{provider} does not use an api_key")
    if base_url and provider != ProviderName.OLLAMA:
        raise ProviderConfigError("base_url is only supported for ollama")


def validate_connection(provider: str, api_key: str | None, base_url: str | None, model: str) -> list[str]:
    """Makes one cheap authenticated call (list models). Raises LLMError if the key is rejected,
    ProviderConfigError if the chosen model is not available to it."""
    models = factory.build_provider(provider, api_key=api_key, base_url=base_url).list_models()
    if model not in models:
        close = [m for m in models if model.split("-")[0] in m][:10] or models[:10]
        raise ProviderConfigError(f"Model '{model}' is not available for this {provider} connection. Try: {close}")
    return models


def create_credential(db: Session, organization_id: uuid.UUID, data: ProviderCreate) -> ProviderCredential:
    api_key = data.api_key.get_secret_value().strip() if data.api_key else None
    _check_config(data.provider, api_key, data.base_url)
    validate_connection(data.provider, api_key, data.base_url, data.default_model)

    credential = ProviderCredential(
        organization_id=organization_id,
        provider=data.provider,
        label=data.label,
        encrypted_api_key=encrypt_secret(api_key) if api_key else None,
        key_hint=secret_hint(api_key) if api_key else None,
        base_url=data.base_url,
        default_model=data.default_model,
        last_validated_at=datetime.now(UTC),
    )
    db.add(credential)
    db.commit()
    return credential


def update_credential(db: Session, credential: ProviderCredential, data: ProviderUpdate) -> ProviderCredential:
    changes = data.model_dump(exclude_unset=True)
    new_key = data.api_key.get_secret_value().strip() if data.api_key else None
    api_key = new_key or (decrypt_secret(credential.encrypted_api_key) if credential.encrypted_api_key else None)
    base_url = changes.get("base_url", credential.base_url)
    model = changes.get("default_model") or credential.default_model

    if new_key or "base_url" in changes or "default_model" in changes:
        _check_config(ProviderName(credential.provider), api_key, base_url)
        validate_connection(credential.provider, api_key, base_url, model)
        credential.last_validated_at = datetime.now(UTC)
    if new_key:
        credential.encrypted_api_key = encrypt_secret(new_key)
        credential.key_hint = secret_hint(new_key)
    for field in ("label", "base_url", "default_model", "is_active"):
        if field in changes and changes[field] is not None:
            setattr(credential, field, changes[field])
    db.commit()
    return credential
