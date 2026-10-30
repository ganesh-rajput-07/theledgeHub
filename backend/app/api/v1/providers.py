from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClientIP, CurrentUser, DbSession, ProviderDep, ProviderManagerDep
from app.api.errors import llm_http_error
from app.llm.base import LLMError
from app.llm.factory import build_provider_for_credential
from app.schemas.provider import ProviderModels, ProviderRead, ProviderUpdate
from app.services import audit_service
from app.services.provider_service import ProviderConfigError, update_credential

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/{provider_id}", response_model=ProviderRead)
def get_provider(access: ProviderDep):
    return access.credential


@router.patch("/{provider_id}", response_model=ProviderRead)
def edit_provider(access: ProviderManagerDep, data: ProviderUpdate, user: CurrentUser, db: DbSession, ip: ClientIP):
    """Rotating the key, URL or default model re-validates before saving. Owners/admins only."""
    try:
        credential = update_credential(db, access.credential, data)
    except ProviderConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except LLMError as exc:
        raise llm_http_error(exc) from exc
    # Record which fields changed - never the key itself.
    changed = sorted(k for k in data.model_dump(exclude_unset=True) if k != "api_key")
    audit_service.record(
        db,
        "provider.update",
        user=user,
        organization_id=credential.organization_id,
        target_type="provider",
        target_id=credential.id,
        ip=ip,
        changed=changed,
        key_rotated=data.api_key is not None,
    )
    return credential


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
def remove_provider(access: ProviderManagerDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    """Deletes the encrypted key. Conversations that used it keep their history but can't ask more."""
    credential = access.credential
    provider_id, org_id, label = credential.id, credential.organization_id, credential.label
    db.delete(credential)
    db.commit()
    audit_service.record(
        db,
        "provider.delete",
        user=user,
        organization_id=org_id,
        target_type="provider",
        target_id=provider_id,
        ip=ip,
        label=label,
    )
