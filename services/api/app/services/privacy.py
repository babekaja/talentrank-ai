"""Fail-closed, tenant-scoped erasure of a candidate and their derived data.

Physical object/vector deletion is required before relational erasure. If an external
store is unavailable, keep DB records and return an error. In-flight workers must
be quiesced operationally before deletion; this is not a globally atomic operation.
"""
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import (Application, ApplicationAssignment, ApplicationReview, AuditLog, Candidate,
    CandidatePortalToken, CandidatePortalSession, CandidateConsentEvent,
    CandidateContact, CandidateLegalHold, CVDocument, DocumentNlpRun, DocumentPage, DocumentFact,
    ExtractionWarning, MatchingCriterionResult, MatchingEvidence, MatchingResult,
    MatchingRun, ProcessingTask, ReportExport, SkillEvidence)
from app.models.auth import utcnow
from app.services.audit import record


def candidate_plan(db: Session, organization_id: str, candidate_id: str) -> dict:
    candidate = db.scalar(select(Candidate).where(Candidate.id == candidate_id,
        Candidate.organization_id == organization_id))
    if not candidate:
        raise HTTPException(404, 'Candidat introuvable')
    applications = db.scalars(select(Application).where(
        Application.candidate_id == candidate_id,
        Application.organization_id == organization_id)).all()
    application_ids = {a.id for a in applications}
    documents = db.scalars(select(CVDocument).where(
        CVDocument.organization_id == organization_id,
        CVDocument.application_id.in_(application_ids))).all() if application_ids else []
    document_ids = {d.id for d in documents}
    assignment_ids = set(db.scalars(select(ApplicationAssignment.id).where(
        ApplicationAssignment.organization_id == organization_id,
        ApplicationAssignment.application_id.in_(application_ids))).all()) if application_ids else set()
    runs = db.scalars(select(MatchingRun).where(MatchingRun.organization_id == organization_id)).all()
    affected_runs = {r.id for r in runs if application_ids.intersection(r.application_ids_snapshot or [])}
    # Also cover results of older or interrupted runs that may lack a complete snapshot.
    if application_ids:
        affected_runs.update(db.scalars(select(MatchingResult.run_id).join(MatchingRun,
            MatchingResult.run_id == MatchingRun.id).where(
            MatchingRun.organization_id == organization_id,
            MatchingResult.application_id.in_(application_ids))).all())
    if document_ids:
        affected_runs.update(db.scalars(select(MatchingRun.id).join(MatchingResult,
            MatchingResult.run_id == MatchingRun.id).join(MatchingCriterionResult,
            MatchingCriterionResult.result_id == MatchingResult.id).join(MatchingEvidence,
            MatchingEvidence.criterion_result_id == MatchingCriterionResult.id).where(
            MatchingRun.organization_id == organization_id,
            MatchingEvidence.document_id.in_(document_ids))).all())
    hold = db.scalar(select(CandidateLegalHold).where(
        CandidateLegalHold.candidate_id == candidate_id,
        CandidateLegalHold.organization_id == organization_id,
        CandidateLegalHold.active.is_(True)))
    return {'candidate': candidate, 'applications': applications,
            'application_ids': application_ids, 'documents': documents,
            'document_ids': document_ids, 'assignment_ids': assignment_ids, 'run_ids': affected_runs,
            'hold': hold}


def plan_summary(plan: dict) -> dict:
    return {'applications': len(plan['application_ids']), 'documents': len(plan['document_ids']),
            'analyses_impactees': len(plan['run_ids']), 'legal_hold': bool(plan['hold']),
            'warning': ('Les analyses communes aux autres candidatures seront supprimées et '
                        'devront être relancées. Les copies déjà exportées, sauvegardes, '
                        'journaux externes et anciens index désactivés exigent des procédures '
                        'de conservation/suppression séparées.')}


def _delete_rows(db: Session, model, column, identifiers):
    if identifiers:
        db.execute(delete(model).where(column.in_(identifiers)))


def purge_candidate(db: Session, actor, candidate_id: str, storage, vector_delete=None) -> dict:
    """Synchronous, small-scale administrator action; no fake success on storage errors.

    vector_delete(organization_id, document_id) is required when semantic is enabled.
    A pending/in-flight worker can re-create derived data, so callers must enforce
    campaign quiescence and operational worker drain before executing purge.
    """
    org_id = actor.organization.id
    candidate = db.scalar(select(Candidate).where(Candidate.id == candidate_id,
        Candidate.organization_id == org_id).with_for_update())
    if not candidate:
        raise HTTPException(404, 'Candidat introuvable')
    plan = candidate_plan(db, org_id, candidate_id)
    if plan['hold']:
        raise HTTPException(409, 'Conservation légale active : suppression interdite')
    # Avoid generating documents or analyses for this candidate while removing assets.
    from app.models import RecruitmentCampaign
    from app.models import ProcessingTask
    for application in plan['applications']:
        campaign = db.scalar(select(RecruitmentCampaign).where(
            RecruitmentCampaign.id == application.campaign_id,
            RecruitmentCampaign.organization_id == org_id))
        if campaign and campaign.status == 'active':
            raise HTTPException(409, 'Clôturer la campagne avant suppression')
    if any(doc.status == 'processing' for doc in plan['documents']):
        raise HTTPException(409, 'Document en cours de traitement')
    if plan['document_ids']:
        nlp_busy = db.scalar(select(DocumentNlpRun.id).where(
            DocumentNlpRun.document_id.in_(plan['document_ids']),
            DocumentNlpRun.status.in_(['processing', 'pending'])).limit(1))
        if nlp_busy:
            raise HTTPException(409, 'Analyse NLP en cours : attendre sa fin')
        busy = db.scalar(select(ProcessingTask.id).where(
            ProcessingTask.document_id.in_(plan['document_ids']),
            ProcessingTask.status.in_(['processing', 'queued'])).limit(1))
        if busy:
            raise HTTPException(409, 'Traitement documentaire en cours : attendre sa fin')
    if plan['run_ids']:
        active = db.scalar(select(MatchingRun.id).where(
            MatchingRun.id.in_(plan['run_ids']),
            MatchingRun.status.in_(['queued', 'running'])).limit(1))
        if active:
            raise HTTPException(409, 'Analyse en cours : attendre sa fin')
    # Delete external derivatives first: any error aborts relational deletion.
    try:
        for doc in plan['documents']:
            if vector_delete is not None:
                vector_delete(org_id, doc.id)
        for doc in plan['documents']:
            # Permanent erasure of historical object versions when supported.
            (storage.purge if hasattr(storage, "purge") else storage.delete)(doc.object_key)
    except Exception:
        db.rollback()
        raise HTTPException(503, 'Suppression externe non confirmée; dossiers conservés en base') from None

    run_ids = plan['run_ids']
    result_ids = set(db.scalars(select(MatchingResult.id).where(
        MatchingResult.run_id.in_(run_ids))).all()) if run_ids else set()
    criterion_ids = set(db.scalars(select(MatchingCriterionResult.id).where(
        MatchingCriterionResult.result_id.in_(result_ids))).all()) if result_ids else set()
    _delete_rows(db, MatchingEvidence, MatchingEvidence.criterion_result_id, criterion_ids)
    _delete_rows(db, MatchingCriterionResult, MatchingCriterionResult.id, criterion_ids)
    _delete_rows(db, MatchingResult, MatchingResult.id, result_ids)
    _delete_rows(db, ReportExport, ReportExport.run_id, run_ids)
    _delete_rows(db, MatchingRun, MatchingRun.id, run_ids)
    _delete_rows(db, DocumentFact, DocumentFact.document_id, plan['document_ids'])
    _delete_rows(db, SkillEvidence, SkillEvidence.document_id, plan['document_ids'])
    _delete_rows(db, DocumentNlpRun, DocumentNlpRun.document_id, plan['document_ids'])
    _delete_rows(db, ExtractionWarning, ExtractionWarning.document_id, plan['document_ids'])
    _delete_rows(db, ProcessingTask, ProcessingTask.document_id, plan['document_ids'])
    _delete_rows(db, DocumentPage, DocumentPage.document_id, plan['document_ids'])
    _delete_rows(db, CVDocument, CVDocument.id, plan['document_ids'])
    _delete_rows(db, ApplicationAssignment, ApplicationAssignment.application_id, plan['application_ids'])
    _delete_rows(db, ApplicationReview, ApplicationReview.application_id, plan['application_ids'])
    _delete_rows(db, Application, Application.id, plan['application_ids'])
    # Explicitly purge portal data; SQLite test databases may not enforce
    # ON DELETE CASCADE, and consent history contains sensitive linkable IDs.
    db.execute(delete(CandidatePortalToken).where(
        CandidatePortalToken.candidate_id == candidate_id,
        CandidatePortalToken.organization_id == org_id))
    db.execute(delete(CandidatePortalSession).where(
        CandidatePortalSession.candidate_id == candidate_id,
        CandidatePortalSession.organization_id == org_id))
    db.execute(delete(CandidateConsentEvent).where(
        CandidateConsentEvent.candidate_id == candidate_id,
        CandidateConsentEvent.organization_id == org_id))
    db.execute(delete(CandidateLegalHold).where(CandidateLegalHold.candidate_id == candidate_id))
    db.execute(delete(CandidateContact).where(CandidateContact.candidate_id == candidate_id))
    db.execute(delete(Candidate).where(Candidate.id == candidate_id,
                                      Candidate.organization_id == org_id))
    # Minimise linkable identifiers in historical application/document/candidate audit entries.
    redacted_ids = plan['document_ids'] | plan['application_ids'] | plan['assignment_ids'] | {candidate_id} | run_ids
    if redacted_ids:
        db.execute(update(AuditLog).where(AuditLog.organization_id == org_id,
            AuditLog.resource_id.in_(redacted_ids)).values(resource_id='redacted', details={}))
    # Export-audit rows reference a removed run through their JSON details.
    if run_ids:
        exported = db.scalars(select(AuditLog).where(
            AuditLog.organization_id == org_id,
            AuditLog.resource_type == 'report_export')).all()
        for item in exported:
            if isinstance(item.details, dict) and item.details.get('run_id') in run_ids:
                item.details = {}
                item.resource_id = 'redacted'
    summary = plan_summary(plan)
    # No candidate identifier in the new audit payload.
    record(db, actor, 'privacy.candidate.erased', 'privacy', 'redacted',
           {'applications': summary['applications'], 'documents': summary['documents'],
            'analyses_impactees': summary['analyses_impactees']})
    db.commit()
    return {'deleted': True, 'applications': summary['applications'],
            'documents': summary['documents'], 'analyses_impactees': summary['analyses_impactees'],
            'external_copies_and_backups': 'not_verified'}
