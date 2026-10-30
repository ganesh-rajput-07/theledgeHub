from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, ProviderDep, ProviderManagerDep
from app.api.errors import llm_http_error
from app.llm.base import LLMError
from app.llm.factory import build_provider_for_credential
from app.schemas.provider import ProviderModels, ProviderRead, ProviderUpdate
from app.services.provider_service import ProviderConfigError, update_credential

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/{provider_id}", response_model=ProviderRead)
def get_provider(access: ProviderDep):
    return access.credential


@router.patch("/{provider_id}", response_model=ProviderRead)
def edit_provider(access: ProviderManagerDep, data: ProviderUpdate, db: DbSession):
    """Rotating the key, URL or default model re-validates before saving. Owners/admins only."""
    try:
        return update_credential(db, access.credential, data)
    except ProviderConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except LLMError as exc:
        raise llm_http_error(exc) from exc


@router.post("/{provider_id}/validate", response_model=ProviderModels)
def validate_provider(access: ProviderDep, db: DbSession):
    """Re-checks the stored key and lists the models it can use."""
    credential = access.credential
    try:
        models = build_provider_for_credential(credential).list_models()
    except LLMError as exc:
        raise llm_http_error(exc) from exc
    credential.last_validated_at = datetime.now(UTC)
    db.commit()
    return ProviderModels(provider_id=credential.id, models=sorted(models))


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider(access: ProviderManagerDep, db: DbSession):
    """Deletes the encrypted key. Conversations that used it keep their history but can't ask more."""
    db.delete(access.credential)
    db.commit()
