from sqlalchemy.orm import Session
from app.core.security import Principal
from app.models import AuditLog


def record(db: Session, actor: Principal, action: str, resource_type: str, resource_id: str, details: dict | None = None):
    """Do not place CV text or personally identifying contact values in audit details."""
    db.add(AuditLog(organization_id=actor.organization.id, actor_id=actor.user.id,
                    action=action, resource_type=resource_type, resource_id=resource_id,
                    details=details or {}))
