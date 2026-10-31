from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import AuditLog

router = APIRouter()


@router.get('/audit-logs')
def audit_logs(limit: int = Query(50, ge=1, le=100),
               actor: Principal = Depends(require_role('org_admin')),
               db: Session = Depends(get_db)):
    logs = db.scalars(select(AuditLog).where(AuditLog.organization_id == actor.organization.id)
                      .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)).all()
    return [{'id': r.id, 'action': r.action, 'actor_id': r.actor_id,
             'resource_type': r.resource_type, 'resource_id': r.resource_id,
             'details': r.details, 'created_at': r.created_at} for r in logs]
