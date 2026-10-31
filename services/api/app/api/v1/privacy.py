"""Administrator-only retention and erasure controls. No automated legal decisions."""
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.documents.storage import PrivateStorage, get_storage
from app.models import Candidate, CandidateLegalHold, RetentionPolicy, Application, RecruitmentCampaign
from app.models.auth import utcnow
from app.services.audit import record
from app.services.privacy import candidate_plan, plan_summary, purge_candidate

router = APIRouter(prefix='/privacy')

class PolicyIn(BaseModel):
    retention_days: int = Field(ge=30, le=3650)

class HoldIn(BaseModel):
    active: bool
    reason: str = Field(min_length=12, max_length=1000)

class EraseIn(BaseModel):
    confirmation: Literal['SUPPRIMER']

@router.get('/retention')
def retention(actor: Principal = Depends(require_role('org_admin')), db: Session = Depends(get_db)):
    row = db.get(RetentionPolicy, actor.organization.id)
    return {'retention_days': row.retention_days if row else 365,
            'configured': bool(row), 'automatic_deletion': False}

@router.put('/retention')
def update_retention(body: PolicyIn, actor: Principal = Depends(require_role('org_admin')),
                     db: Session = Depends(get_db)):
    row = db.get(RetentionPolicy, actor.organization.id)
    if row is None:
        row = RetentionPolicy(organization_id=actor.organization.id,
                              retention_days=body.retention_days,updated_by=actor.user.id)
        db.add(row)
    else:
        row.retention_days = body.retention_days
        row.updated_by = actor.user.id
        row.updated_at = utcnow()
    record(db, actor, 'privacy.retention.updated', 'retention_policy', actor.organization.id,
           {'retention_days': body.retention_days})
    db.commit()
    return {'retention_days': row.retention_days, 'automatic_deletion': False}

@router.put('/candidates/{candidate_id}/hold')
def update_hold(candidate_id: str, body: HoldIn,
                actor: Principal = Depends(require_role('org_admin')), db: Session = Depends(get_db)):
    candidate_plan(db,actor.organization.id,candidate_id)
    row = db.get(CandidateLegalHold,candidate_id)
    if row is not None and row.organization_id != actor.organization.id:
        raise HTTPException(404, 'Candidat introuvable')
    if row is None:
        row=CandidateLegalHold(candidate_id=candidate_id,organization_id=actor.organization.id,
                               active=body.active,reason=body.reason,updated_by=actor.user.id)
        db.add(row)
    else:
        row.active=body.active
        row.reason=body.reason
        row.updated_by=actor.user.id
        row.updated_at=utcnow()
    record(db,actor,'privacy.hold.updated','candidate',candidate_id,{'active': body.active})
    db.commit()
    return {'active':row.active}

@router.get('/candidates/due')
def due_candidates(limit:int=Query(50,ge=1,le=100),
         actor: Principal=Depends(require_role('org_admin')),db:Session=Depends(get_db)):
    policy=db.get(RetentionPolicy,actor.organization.id)
    days=policy.retention_days if policy else 365
    cutoff=utcnow()-timedelta(days=days)
    due=[]
    # Keyset pagination: the 501st oldest person may be the first eligible one.
    # A hard 500-row cap silently hides due candidates in active organisations.
    cursor=None
    while len(due)<limit:
        q=select(Candidate).where(Candidate.organization_id==actor.organization.id,
                Candidate.created_at<cutoff)
        if cursor is not None:
            from sqlalchemy import tuple_
            q=q.where(tuple_(Candidate.created_at,Candidate.id)>cursor)
        rows=db.scalars(q.order_by(Candidate.created_at,Candidate.id).limit(100)).all()
        if not rows:
            break
        for c in rows:
            cursor=(c.created_at,c.id)
            plan=candidate_plan(db,actor.organization.id,c.id)
            if plan['hold']:continue
            applications=plan['applications']
            if any(a.created_at >= cutoff for a in applications):continue
            if plan['documents'] and any(d.created_at >= cutoff for d in plan['documents']):continue
            if applications:
                campaigns=db.scalars(select(RecruitmentCampaign).where(
                    RecruitmentCampaign.organization_id==actor.organization.id,
                    RecruitmentCampaign.id.in_([a.campaign_id for a in applications]))).all()
                if any(x.status != 'closed' for x in campaigns):continue
            due.append({'id':c.id,'reference':c.reference,'created_at':c.created_at,
                        'documents':len(plan['document_ids'])})
            if len(due)>=limit:break
        if len(rows)<100:
            break
    return {'cutoff':cutoff,'items':due,'automatic_deletion':False,
            'notice':'Liste prévisionnelle; vérifier les obligations légales avant suppression.'}

@router.get('/candidates/{candidate_id}/erasure-preview')
def erasure_preview(candidate_id:str,actor:Principal=Depends(require_role('org_admin')),
                    db:Session=Depends(get_db)):
    return plan_summary(candidate_plan(db,actor.organization.id,candidate_id))

@router.post('/candidates/{candidate_id}/erase')
def erase(candidate_id:str, body:EraseIn,
          actor:Principal=Depends(require_role('org_admin')),
          db:Session=Depends(get_db), storage:PrivateStorage=Depends(get_storage)):
    from app.ml.remote import ml_request
    settings=get_settings()
    def vector_delete(org_id:str, doc_id:str):
        return ml_request('/private/delete',{'organization_id':org_id,'document_id':doc_id})
    return purge_candidate(db,actor,candidate_id,storage,
                           vector_delete if settings.semantic_enabled else None)
