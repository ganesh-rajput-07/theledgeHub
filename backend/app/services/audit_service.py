import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    action: str,
    *,
    user: User | None = None,
    email: str | None = None,
    organization_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    ip: str | None = None,
    **details,
) -> None:
    """Append an audit entry. Never store secrets (keys, passwords, tokens) in `details`."""
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user.id if user else None,
            actor_email=user.email if user else email,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            ip_address=ip,
            details=details,
        )
    )
    db.commit()
