"""Phase 2 captures human-entered candidates; no CV parsing is implied."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Application, ApplicationReview, Candidate, CandidateContact,
                        RecruitmentCampaign)
from app.models.auth import uid
from app.schemas.recruitment import (ApplicationIn, ApplicationOut, CandidateIn,
                                     CandidateOut, ReviewIn, ReviewOut)
from app.services.audit import record

router = APIRouter()


def as_candidate(row: Candidate) -> CandidateOut:
    return CandidateOut(id=row.id, reference=row.reference, full_name=row.full_name,
                        email=row.contacts.email if row.contacts else None,
                        phone=row.contacts.phone if row.contacts else None,
                        created_at=row.created_at)


@router.get('/candidates')
def list_candidates(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                    q: str | None = Query(default=None, max_length=120),
                    actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                    db: Session = Depends(get_db)):
    clauses = [Candidate.organization_id == actor.organization.id]
    if q:
        clauses.append(Candidate.full_name.ilike('%' + q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%', escape='\\'))
    total = db.scalar(select(func.count()).select_from(Candidate).where(*clauses)) or 0
    rows = db.scalars(select(Candidate).options(selectinload(Candidate.contacts)).where(*clauses)
                      .order_by(Candidate.created_at.desc(), Candidate.id.desc())
                      .offset(offset).limit(limit)).all()
    return {'items': [as_candidate(r) for r in rows], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/candidates', response_model=CandidateOut, status_code=201)
def create_candidate(body: CandidateIn,
                     actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                     db: Session = Depends(get_db)):
    row = Candidate(organization_id=actor.organization.id, full_name=body.full_name,
                    reference=f'TR-{uid()[:8].upper()}')
    row.contacts = CandidateContact(email=str(body.email).lower() if body.email else None,
                                    phone=body.phone)
    db.add(row)
    db.flush()
    record(db, actor, 'candidate.created', 'candidate', row.id)
    db.commit()
    db.refresh(row)
    return as_candidate(row)


@router.get('/candidates/{candidate_id}', response_model=CandidateOut)
def get_candidate(candidate_id: str,
                  actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                  db: Session = Depends(get_db)):
    row = db.scalar(select(Candidate).options(selectinload(Candidate.contacts)).where(
        Candidate.id == candidate_id, Candidate.organization_id == actor.organization.id))
    if not row:
        raise HTTPException(404, 'Candidat introuvable')
    return as_candidate(row)


@router.get('/applications')
def list_applications(campaign_id: str | None = None,
                      limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                      actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                      db: Session = Depends(get_db)):
    clauses = [Application.organization_id == actor.organization.id]
    if campaign_id:
        clauses.append(Application.campaign_id == campaign_id)
    total = db.scalar(select(func.count()).select_from(Application)
       .join(Candidate, Candidate.id == Application.candidate_id)
       .join(RecruitmentCampaign, RecruitmentCampaign.id == Application.campaign_id)
       .where(*clauses, Candidate.organization_id == actor.organization.id,
              RecruitmentCampaign.organization_id == actor.organization.id)) or 0
    rows = db.execute(select(Application, Candidate.reference, Candidate.full_name,
                            RecruitmentCampaign.name)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(RecruitmentCampaign, RecruitmentCampaign.id == Application.campaign_id)
        .where(*clauses, Candidate.organization_id == actor.organization.id,
               RecruitmentCampaign.organization_id == actor.organization.id)
        .order_by(Application.created_at.desc(), Application.id.desc())
        .offset(offset).limit(limit)).all()
    return {'items': [{**ApplicationOut.model_validate(row).model_dump(mode='json'),
                       'candidate_reference': reference, 'candidate_name': name,
                       'campaign_name': campaign}
                      for row, reference, name, campaign in rows],
            'total': total, 'limit': limit, 'offset': offset}


@router.post('/applications', response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationIn,
                       actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                       db: Session = Depends(get_db)):
    campaign = db.scalar(select(RecruitmentCampaign).where(
        RecruitmentCampaign.id == body.campaign_id,
        RecruitmentCampaign.organization_id == actor.organization.id))
    candidate = db.scalar(select(Candidate).where(
        Candidate.id == body.candidate_id,
        Candidate.organization_id == actor.organization.id))
    if not campaign or not candidate:
        raise HTTPException(404, 'Campagne ou candidat introuvable')
    if campaign.status != 'active':
        raise HTTPException(409, 'La campagne doit être active')
    row = Application(organization_id=actor.organization.id, campaign_id=campaign.id,
                      candidate_id=candidate.id)
    db.add(row)
    try:
        db.flush()
        record(db, actor, 'application.created', 'application', row.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Candidature déjà liée à cette campagne') from None
    db.refresh(row)
    return row


@router.post('/applications/{application_id}/reviews', response_model=ReviewOut, status_code=201)
def add_review(application_id: str, body: ReviewIn,
               actor: Principal = Depends(require_role('org_admin', 'recruiter')),
               db: Session = Depends(get_db)):
    application = db.scalar(select(Application).where(
        Application.id == application_id,
        Application.organization_id == actor.organization.id).with_for_update())
    if not application:
        raise HTTPException(404, 'Candidature introuvable')
    review = ApplicationReview(application_id=application.id, author_id=actor.user.id,
                               finding=body.finding, note=body.note)
    application.review_status = body.finding
    db.add(review)
    db.flush()
    record(db, actor, 'application.reviewed', 'application', application.id,
           {'finding': body.finding})
    db.commit()
    db.refresh(review)
    return review


@router.get('/applications/{application_id}/reviews', response_model=list[ReviewOut])
def get_reviews(application_id: str,
                actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                db: Session = Depends(get_db)):
    application = db.scalar(select(Application).where(
        Application.id == application_id,
        Application.organization_id == actor.organization.id))
    if not application:
        raise HTTPException(404, 'Candidature introuvable')
    return db.scalars(select(ApplicationReview).where(
        ApplicationReview.application_id == application.id)
        .order_by(ApplicationReview.created_at.desc())).all()
