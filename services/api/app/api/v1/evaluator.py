"""Tenant-scoped human review workflow with masked identities.

Evaluators receive only assigned dossiers and short, source-checked excerpts.
Their independent review does not change the recruiter's application status.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Application, ApplicationAssignment, ApplicationReview, Candidate,
                        CVDocument, DocumentPage, OrganizationMember, User, RecruitmentCampaign,
                        SkillEvidence)
from app.models.auth import utcnow
from app.schemas.recruitment import ReviewIn
from app.services.audit import record

router = APIRouter(prefix='/evaluator')


class AssignmentIn(BaseModel):
    application_id: str = Field(min_length=1, max_length=36)
    evaluator_member_id: str = Field(min_length=1, max_length=36)


def _assignment(db: Session, org_id: str, assignment_id: str) -> ApplicationAssignment:
    row = db.scalar(select(ApplicationAssignment).where(
        ApplicationAssignment.id == assignment_id,
        ApplicationAssignment.organization_id == org_id))
    if not row:
        raise HTTPException(404, 'Affectation introuvable')
    return row


def _masked(db: Session, row: ApplicationAssignment) -> dict:
    # Never serialize Candidate.full_name or CandidateContact here.
    application = db.scalar(select(Application).where(
        Application.id == row.application_id,
        Application.organization_id == row.organization_id))
    if not application:
        raise HTTPException(404, 'Candidature introuvable')
    candidate = db.scalar(select(Candidate).where(
        Candidate.id == application.candidate_id,
        Candidate.organization_id == row.organization_id))
    campaign = db.scalar(select(RecruitmentCampaign).where(
        RecruitmentCampaign.id == application.campaign_id,
        RecruitmentCampaign.organization_id == row.organization_id))
    if not candidate or not campaign:
        raise HTTPException(404, 'Dossier introuvable')
    return {'id': row.id, 'application_id': row.application_id,
            'evaluator_member_id': row.evaluator_member_id,
            'candidate_reference': candidate.reference, 'campaign_name': campaign.name,
            'status': row.status, 'created_at': row.created_at,
            'completed_at': row.completed_at, 'revoked_at': row.revoked_at}


@router.get('/members')
def active_evaluators(actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                      db: Session = Depends(get_db)):
    return [{'id': m.id, 'user_id': m.user_id, 'label': u.full_name}
            for m, u in db.execute(select(OrganizationMember, User).join(User, User.id == OrganizationMember.user_id).where(
                OrganizationMember.organization_id == actor.organization.id,
                OrganizationMember.is_active.is_(True),
                OrganizationMember.role == 'evaluator').order_by(User.full_name)).all()]


@router.get('/assignable-applications')
def assignable_applications(limit: int = Query(25, ge=1, le=100),
                            offset: int = Query(0, ge=0),
                            q: str = Query('', max_length=80),
                            actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                            db: Session = Depends(get_db)):
    clauses = [Application.organization_id == actor.organization.id,
               Candidate.organization_id == actor.organization.id,
               RecruitmentCampaign.organization_id == actor.organization.id]
    if q.strip():
        term = '%' + q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        clauses.append(Candidate.reference.ilike(term, escape='\\'))
    selection = (select(Application, Candidate.reference, RecruitmentCampaign.name)
                 .join(Candidate, Candidate.id == Application.candidate_id)
                 .join(RecruitmentCampaign, RecruitmentCampaign.id == Application.campaign_id))
    total = db.scalar(select(func.count()).select_from(Application)
                      .join(Candidate, Candidate.id == Application.candidate_id)
                      .join(RecruitmentCampaign, RecruitmentCampaign.id == Application.campaign_id)
                      .where(*clauses)) or 0
    rows = db.execute(selection.where(*clauses)
                      .order_by(Application.created_at.desc(), Application.id.desc())
                      .offset(offset).limit(limit)).all()
    return {'items': [{'application_id': a.id, 'candidate_reference': ref,
                       'campaign_name': name} for a, ref, name in rows],
            'total': total, 'offset': offset, 'limit': limit}


@router.post('/assignments', status_code=201)
def assign(body: AssignmentIn,
           actor: Principal = Depends(require_role('org_admin', 'recruiter')),
           db: Session = Depends(get_db)):
    application = db.scalar(select(Application).where(
        Application.id == body.application_id,
        Application.organization_id == actor.organization.id).with_for_update())
    member = db.scalar(select(OrganizationMember).where(
        OrganizationMember.id == body.evaluator_member_id,
        OrganizationMember.organization_id == actor.organization.id,
        OrganizationMember.role == 'evaluator',
        OrganizationMember.is_active.is_(True)))
    if not application or not member:
        raise HTTPException(404, 'Candidature ou évaluateur introuvable')
    old = db.scalar(select(ApplicationAssignment).where(
        ApplicationAssignment.application_id == application.id,
        ApplicationAssignment.evaluator_member_id == member.id).with_for_update())
    if old and old.status != 'revoked':
        raise HTTPException(409, 'Cette affectation existe déjà')
    if old:
        old.status, old.revoked_at, old.completed_at = 'assigned', None, None
        row = old
    else:
        row = ApplicationAssignment(organization_id=actor.organization.id,
                                    application_id=application.id, evaluator_member_id=member.id,
                                    assigned_by=actor.user.id, status='assigned')
        db.add(row)
    try:
        db.flush()
        record(db, actor, 'assignment.created', 'application_assignment', row.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Affectation concurrente déjà enregistrée') from None
    return _masked(db, row)


@router.get('/assignments')
def list_assignments(limit: int = Query(25, ge=1, le=100),
                     offset: int = Query(0, ge=0),
                     application_id: str | None = None,
                     actor: Principal = Depends(require_role('org_admin', 'recruiter', 'evaluator')),
                     db: Session = Depends(get_db)):
    clauses = [ApplicationAssignment.organization_id == actor.organization.id]
    if actor.role == 'evaluator':
        # Joined membership guards a membership change or revocation without relying on a JWT role alone.
        clauses += [OrganizationMember.user_id == actor.user.id,
                    OrganizationMember.role == 'evaluator',
                    OrganizationMember.is_active.is_(True),
                    ApplicationAssignment.evaluator_member_id == OrganizationMember.id,
                    ApplicationAssignment.status != 'revoked']
    if application_id:
        clauses.append(ApplicationAssignment.application_id == application_id)
    stmt = select(ApplicationAssignment)
    count_stmt = select(func.count()).select_from(ApplicationAssignment)
    if actor.role == 'evaluator':
        stmt = stmt.join(OrganizationMember, OrganizationMember.id == ApplicationAssignment.evaluator_member_id)
        count_stmt = count_stmt.join(OrganizationMember, OrganizationMember.id == ApplicationAssignment.evaluator_member_id)
    total = db.scalar(count_stmt.where(*clauses)) or 0
    rows = db.scalars(stmt.where(*clauses).order_by(ApplicationAssignment.created_at.desc(),
                                                  ApplicationAssignment.id.desc())
                      .offset(offset).limit(limit)).all()
    return {'items': [_masked(db, r) for r in rows], 'total': total,
            'offset': offset, 'limit': limit}


def _my_assignment(db: Session, actor: Principal, assignment_id: str, lock: bool = False):
    stmt = select(ApplicationAssignment).join(OrganizationMember,
        OrganizationMember.id == ApplicationAssignment.evaluator_member_id).where(
        ApplicationAssignment.id == assignment_id,
        ApplicationAssignment.organization_id == actor.organization.id,
        ApplicationAssignment.status.in_(('assigned', 'completed')),
        OrganizationMember.organization_id == actor.organization.id,
        OrganizationMember.user_id == actor.user.id,
        OrganizationMember.role == 'evaluator',
        OrganizationMember.is_active.is_(True))
    row = db.scalar(stmt.with_for_update() if lock else stmt)
    if not row:
        raise HTTPException(404, 'Dossier non affecté ou accès révoqué')
    return row


@router.get('/assignments/{assignment_id}')
def assignment_detail(assignment_id: str,
                      actor: Principal = Depends(require_role('org_admin', 'recruiter', 'evaluator')),
                      db: Session = Depends(get_db)):
    row = (_my_assignment(db, actor, assignment_id) if actor.role == 'evaluator'
           else _assignment(db, actor.organization.id, assignment_id))
    return _masked(db, row)


@router.post('/assignments/{assignment_id}/revoke')
def revoke(assignment_id: str,
           actor: Principal = Depends(require_role('org_admin', 'recruiter')),
           db: Session = Depends(get_db)):
    row = _assignment(db, actor.organization.id, assignment_id)
    if row.status == 'revoked':
        raise HTTPException(409, 'Affectation déjà révoquée')
    row.status, row.revoked_at = 'revoked', utcnow()
    record(db, actor, 'assignment.revoked', 'application_assignment', row.id)
    db.commit()
    return {'id': row.id, 'status': row.status}


@router.get('/assignments/{assignment_id}/evidence')
def assignment_evidence(assignment_id: str,
                        actor: Principal = Depends(require_role('evaluator')),
                        db: Session = Depends(get_db)):
    row = _my_assignment(db, actor, assignment_id)
    document_ids = db.scalars(select(CVDocument.id).where(
        CVDocument.organization_id == actor.organization.id,
        CVDocument.application_id == row.application_id)).all()
    if not document_ids:
        return {'items': [], 'warning': 'Aucun document analysé pour cette candidature.'}
    evidence = db.execute(select(SkillEvidence, DocumentPage).join(DocumentPage,
        DocumentPage.id == SkillEvidence.page_id).where(
        SkillEvidence.organization_id == actor.organization.id,
        SkillEvidence.document_id.in_(document_ids),
        DocumentPage.document_id == SkillEvidence.document_id)
        .order_by(SkillEvidence.id).limit(100)).all()
    items = []
    for mention, page in evidence:
        # No false excerpt: fail closed if the source offsets no longer match.
        if (not 0 <= mention.start_offset < mention.end_offset <= len(page.text)
                or page.text[mention.start_offset:mention.end_offset] != mention.matched_text):
            continue
        # Avoid leaking the entire CV: a short local snippet, not contact details or full pages.
        # Reject passages that may include private contact data around the matched word.
        items.append({'page_number': page.page_number, 'excerpt': mention.matched_text,
                      'status': mention.status, 'context_code': mention.context_code,
                      'skill_id': mention.skill_id})
    record(db, actor, 'assignment.evidence.viewed', 'application_assignment', row.id)
    db.commit()
    return {'items': items, 'warning': 'Mentions automatiques : vérifier le contexte dans le dossier source avant toute conclusion.'}


@router.post('/assignments/{assignment_id}/reviews', status_code=201)
def evaluator_review(assignment_id: str, body: ReviewIn,
                     actor: Principal = Depends(require_role('evaluator')),
                     db: Session = Depends(get_db)):
    row = _my_assignment(db, actor, assignment_id, lock=True)
    if row.status != 'assigned':
        raise HTTPException(409, 'Affectation déjà examinée')
    review = ApplicationReview(application_id=row.application_id,
                               author_id=actor.user.id, finding=body.finding, note=body.note)
    db.add(review)
    row.status, row.completed_at = 'completed', utcnow()
    # Intentionally leave Application.review_status unchanged: each human reviewer is independent.
    db.flush()
    record(db, actor, 'assignment.reviewed', 'application_assignment', row.id,
           {'finding': body.finding})
    db.commit()
    return {'assignment_id': row.id, 'review_id': review.id, 'status': row.status}
