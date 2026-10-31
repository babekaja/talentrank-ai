from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import Job, RecruitmentCampaign
from app.schemas.recruitment import CampaignIn, CampaignOut, CampaignStatusIn
from app.services.audit import record

router = APIRouter()


@router.get('/campaigns')
def list_campaigns(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                   q: str | None = Query(default=None, max_length=120),
                   actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                   db: Session = Depends(get_db)):
    clauses = [RecruitmentCampaign.organization_id == actor.organization.id]
    if q:
        search = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        clauses.append(RecruitmentCampaign.name.ilike('%' + search + '%', escape='\\'))
    total = db.scalar(select(func.count()).select_from(RecruitmentCampaign).where(*clauses)) or 0
    rows = db.scalars(select(RecruitmentCampaign).where(*clauses)
                      .order_by(RecruitmentCampaign.created_at.desc(), RecruitmentCampaign.id.desc())
                      .offset(offset).limit(limit)).all()
    return {'items': [CampaignOut.model_validate(r) for r in rows], 'total': total, 'limit': limit, 'offset': offset}


@router.get('/campaigns/{campaign_id}', response_model=CampaignOut)
def get_campaign(campaign_id: str,
                 actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                 db: Session = Depends(get_db)):
    row = db.scalar(select(RecruitmentCampaign).where(
        RecruitmentCampaign.id == campaign_id,
        RecruitmentCampaign.organization_id == actor.organization.id))
    if row is None:
        raise HTTPException(404, 'Campagne introuvable')
    return row


@router.post('/campaigns', response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignIn,
                    actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                    db: Session = Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == body.job_id,
                 Job.organization_id == actor.organization.id))
    if not job:
        raise HTTPException(404, 'Offre introuvable')
    if not job.criteria_confirmed_at:
        raise HTTPException(409, 'Les critères de l’offre doivent être confirmés')
    row = RecruitmentCampaign(organization_id=actor.organization.id, job_id=job.id,
                              name=body.name, created_by=actor.user.id)
    db.add(row)
    db.flush()
    record(db, actor, 'campaign.created', 'campaign', row.id, {'job_id': job.id})
    db.commit()
    db.refresh(row)
    return row


@router.patch('/campaigns/{campaign_id}/status', response_model=CampaignOut)
def update_campaign_status(campaign_id: str, body: CampaignStatusIn,
                           actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                           db: Session = Depends(get_db)):
    campaign = db.scalar(select(RecruitmentCampaign).where(
        RecruitmentCampaign.id == campaign_id,
        RecruitmentCampaign.organization_id == actor.organization.id).with_for_update())
    if not campaign:
        raise HTTPException(404, 'Campagne introuvable')
    allowed = {'planned': {'active', 'closed'}, 'active': {'closed'}, 'closed': set()}
    if body.status not in allowed[campaign.status]:
        raise HTTPException(409, 'Transition de statut non autorisée')
    campaign.status = body.status
    if body.status == 'active':
        job = db.scalar(select(Job).where(Job.id == campaign.job_id,
                                         Job.organization_id == actor.organization.id))
        if not job or not job.criteria_confirmed_at:
            raise HTTPException(409, 'Critères non confirmés')
        job.status = 'open'
    if body.status == 'closed':
        # An offer can remain open when another active campaign is running.
        other_active = db.scalar(select(RecruitmentCampaign.id).where(
            RecruitmentCampaign.job_id == campaign.job_id,
            RecruitmentCampaign.organization_id == actor.organization.id,
            RecruitmentCampaign.id != campaign.id,
            RecruitmentCampaign.status == 'active').limit(1))
        if not other_active:
            job = db.scalar(select(Job).where(Job.id == campaign.job_id,
                                             Job.organization_id == actor.organization.id))
            if job:
                job.status = 'closed'
    record(db, actor, 'campaign.status.updated', 'campaign', campaign.id, {'status': body.status})
    db.commit()
    db.refresh(campaign)
    return campaign
