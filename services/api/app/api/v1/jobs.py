"""Job descriptions and human-approved, versioned job requirements."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import Job, JobRequirement, RecruitmentCampaign
from app.models.auth import utcnow
from app.schemas.recruitment import (ConfirmRequirementsIn, JobIn, JobOut, JobUpdate,
                                     RequirementsReplace)
from app.services.audit import record
from app.ml.matching_service import requirement_snapshot, resolve_skills

router = APIRouter()


def job_or_404(db: Session, actor: Principal, job_id: str, *, lock: bool = False) -> Job:
    q = select(Job).options(selectinload(Job.requirements)).where(
        Job.id == job_id, Job.organization_id == actor.organization.id)
    if lock:
        q = q.with_for_update()
    job = db.scalar(q)
    if not job:
        raise HTTPException(404, 'Offre introuvable')
    mapping = resolve_skills(db, requirement_snapshot(job))
    for requirement in job.requirements:
        requirement.resolved_skill_id = mapping.get(requirement.id)
    return job


def protect_criteria_edit(db: Session, job: Job):
    campaign = db.scalar(select(RecruitmentCampaign.id).where(
        RecruitmentCampaign.organization_id == job.organization_id,
        RecruitmentCampaign.job_id == job.id,
        RecruitmentCampaign.status.in_(['active', 'closed'])).limit(1))
    if campaign:
        raise HTTPException(409, 'Critères verrouillés : campagne active ou clôturée')


@router.get('/jobs')
def list_jobs(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
              q: str | None = Query(default=None, max_length=120),
              actor: Principal = Depends(require_role('org_admin', 'recruiter')),
              db: Session = Depends(get_db)):
    clauses = [Job.organization_id == actor.organization.id]
    if q:
        search = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        clauses.append(Job.title.ilike('%' + search + '%', escape='\\'))
    total = db.scalar(select(func.count()).select_from(Job).where(*clauses)) or 0
    items = db.scalars(select(Job).options(selectinload(Job.requirements)).where(*clauses)
                       .order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit)).all()
    return {'items': [JobOut.model_validate(v) for v in items], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/jobs', response_model=JobOut, status_code=201)
def create_job(body: JobIn, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
               db: Session = Depends(get_db)):
    row = Job(organization_id=actor.organization.id, created_by=actor.user.id,
              **body.model_dump())
    db.add(row)
    db.flush()
    record(db, actor, 'job.created', 'job', row.id)
    db.commit()
    return job_or_404(db, actor, row.id)


@router.get('/jobs/{job_id}', response_model=JobOut)
def get_job(job_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
            db: Session = Depends(get_db)):
    return job_or_404(db, actor, job_id)


@router.patch('/jobs/{job_id}', response_model=JobOut)
def patch_job(job_id: str, body: JobUpdate,
              actor: Principal = Depends(require_role('org_admin', 'recruiter')),
              db: Session = Depends(get_db)):
    row = job_or_404(db, actor, job_id, lock=True)
    protect_criteria_edit(db, row)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return row
    fields = {**{k: getattr(row, k) for k in JobIn.model_fields}, **changes}
    JobIn.model_validate(fields)
    for key, value in changes.items():
        setattr(row, key, value)
    # Human reconfirmation needed after substantive edits to the job.
    row.criteria_confirmed_at = None
    row.criteria_confirmed_by = None
    row.status = 'draft'
    record(db, actor, 'job.updated', 'job', row.id, {'fields': list(changes)})
    db.commit()
    return job_or_404(db, actor, row.id)


@router.put('/jobs/{job_id}/requirements', response_model=JobOut)
def replace_requirements(job_id: str, body: RequirementsReplace,
                         actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                         db: Session = Depends(get_db)):
    row = job_or_404(db, actor, job_id, lock=True)
    protect_criteria_edit(db, row)
    row.requirements.clear()
    db.flush()
    row.requirements.extend(JobRequirement(**r.model_dump()) for r in body.items)
    row.criteria_version += 1
    row.criteria_confirmed_at = None
    row.criteria_confirmed_by = None
    row.status = 'draft'
    record(db, actor, 'job.requirements.replaced', 'job', row.id,
           {'criteria_version': row.criteria_version, 'count': len(body.items)})
    db.commit()
    return job_or_404(db, actor, row.id)


@router.post('/jobs/{job_id}/requirements/confirm', response_model=JobOut)
def confirm_requirements(job_id: str, body: ConfirmRequirementsIn,
                         actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                         db: Session = Depends(get_db)):
    row = job_or_404(db, actor, job_id, lock=True)
    protect_criteria_edit(db, row)
    if row.criteria_version != body.expected_version:
        raise HTTPException(409, 'Version des critères obsolète : actualisez l’offre')
    if not row.requirements or not any(r.required for r in row.requirements):
        raise HTTPException(422, 'Au moins un critère essentiel est nécessaire')
    row.criteria_confirmed_at = utcnow()
    row.criteria_confirmed_by = actor.user.id
    record(db, actor, 'job.requirements.confirmed', 'job', row.id,
           {'criteria_version': row.criteria_version})
    db.commit()
    return job_or_404(db, actor, row.id)
