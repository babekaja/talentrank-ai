"""Database adapter for pure matching. Tenant scope is repeated on every lookup."""
import unicodedata
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.ml.matching import ALGORITHM_VERSION, calculate, stable_hash
from app.models import (Application, CVDocument, DocumentNlpRun, DocumentPage, Job,
                        MatchingRun, MatchingResult, MatchingCriterionResult, MatchingEvidence,
                        Skill, SkillAlias, SkillEvidence)
from app.models.auth import utcnow


def requirement_snapshot(job: Job) -> list[dict]:
    return sorted([{'id':r.id, 'code':r.code, 'label':r.label, 'category':r.category,
                    'required':r.required, 'weight':r.weight, 'justification':r.justification,
                    'skill_ref':r.skill_ref} for r in job.requirements], key=lambda r: r['id'])


def resolve_skills(db: Session, requirements: list[dict]) -> dict[str, str | None]:
    """Résoudre les références, puis les libellés et alias vérifiés exacts et uniques."""
    skills = db.scalars(select(Skill).where(Skill.active.is_(True))).all()
    by_id = {skill.id: skill.id for skill in skills}
    by_code = {skill.code.casefold(): skill.id for skill in skills}

    def exact(value):
        # Conserver les signes qui distinguent C, C++, C# ou .NET.
        return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())

    labels: dict[str, set[str]] = {}
    def add_label(label, skill_id):
        key = exact(label)
        if key:
            labels.setdefault(key, set()).add(skill_id)
    for skill in skills:
        add_label(skill.label_fr, skill.id)
        add_label(skill.label_en, skill.id)
    aliases = db.execute(select(SkillAlias.normalized_alias, SkillAlias.skill_id)
        .join(Skill, Skill.id == SkillAlias.skill_id)
        .where(Skill.active.is_(True), SkillAlias.verified.is_(True))).all()
    for label, skill_id in aliases:
        add_label(label, skill_id)
    mapping = {}
    for requirement in requirements:
        skill_id = None
        if requirement['category'] == 'skill':
            reference = requirement.get('skill_ref')
            if reference:
                # Une référence explicite inconnue ou inactive reste à vérifier.
                skill_id = by_id.get(reference) or by_code.get(reference.casefold())
            else:
                skill_id = by_code.get(requirement['code'].casefold())
                if skill_id is None:
                    matches = labels.get(exact(requirement['label']), set())
                    if len(matches) == 1:
                        skill_id = next(iter(matches))
        mapping[requirement['id']] = skill_id
    return mapping


def applicant_inputs(db: Session, run: MatchingRun, app: Application):
    documents = db.scalars(select(CVDocument).where(
        CVDocument.organization_id == run.organization_id,
        CVDocument.application_id == app.id,
        CVDocument.campaign_id == run.campaign_id).order_by(CVDocument.id)).all()
    ready = bool(documents)
    doc_state = []
    evidence_by_skill: dict[str, list[dict]] = {}
    documents_review = False
    for document in documents:
        nlp = db.scalar(select(DocumentNlpRun).where(
            DocumentNlpRun.document_id == document.id,
            DocumentNlpRun.organization_id == run.organization_id))
        if document.status not in ('completed', 'needs_review') or not nlp or nlp.status != 'completed':
            ready = False
        if document.status == 'needs_review':
            documents_review = True
        doc_state.append({'id':document.id, 'sha256':document.sha256, 'status':document.status,
                          'nlp': nlp.status if nlp else None,
                          'rules': nlp.rules_version if nlp else None,
                          'taxonomy': nlp.taxonomy_fingerprint if nlp else None,
                          'content': nlp.content_fingerprint if nlp else None})
    doc_ids = [d.id for d in documents]
    if doc_ids:
        rows = db.execute(select(SkillEvidence, DocumentPage).join(
            DocumentPage, DocumentPage.id == SkillEvidence.page_id).where(
            SkillEvidence.organization_id == run.organization_id,
            SkillEvidence.document_id.in_(doc_ids),
            DocumentPage.document_id == SkillEvidence.document_id)).all()
        for e, page in rows:
            source_valid = (0 <= e.start_offset < e.end_offset <= len(page.text)
                            and page.text[e.start_offset:e.end_offset] == e.matched_text)
            evidence_by_skill.setdefault(e.skill_id, []).append({
                'id':e.id, 'document_id':e.document_id, 'page_id':page.id,
                'page_number':page.page_number, 'start_offset':e.start_offset,
                'end_offset':e.end_offset, 'matched_text':e.matched_text,
                'status':e.status, 'rules_version':e.rules_version,
                'source_valid':source_valid})
    for evidences in evidence_by_skill.values():
        evidences.sort(key=lambda e: e['id'])
    return ready, documents_review, stable_hash(doc_state), evidence_by_skill


def calculate_application(db: Session, run: MatchingRun, application: Application,
                          skill_mapping: dict[str, str | None]):
    ready, documents_review, document_fp, evidences = applicant_inputs(db, run, application)
    score = calculate(run.requirements_snapshot, run.weights_snapshot, evidences, skill_mapping,
                      documents_ready=ready, document_fingerprint=document_fp)
    if documents_review and score.score is not None and score.state == 'documentary_coverage':
        from dataclasses import replace
        score = replace(score, state='partial_review_required')
    result = MatchingResult(run_id=run.id, application_id=application.id,
            candidate_id=application.candidate_id, score=score.score, state=score.state,
            documented=sum(c.state == 'documented_mention' for c in score.criteria),
            to_review=sum(c.state in ('needs_review','manual_review_required','awaiting_documents') for c in score.criteria),
            not_documented=sum(c.state == 'not_documented' for c in score.criteria),
            evidence_fingerprint=score.fingerprint, group_coverage=score.group_coverage)
    db.add(result)
    db.flush()
    for criterion in score.criteria:
        cr = MatchingCriterionResult(result_id=result.id, requirement_id=criterion.requirement['id'],
                code=criterion.requirement['code'], label=criterion.requirement['label'],
                group_code=criterion.group, state=criterion.state,
                weight=criterion.requirement['weight'], contribution=criterion.contribution,
                note_code=criterion.note_code)
        db.add(cr)
        db.flush()
        if criterion.evidence:
            e = criterion.evidence
            db.add(MatchingEvidence(criterion_result_id=cr.id, evidence_id=e['id'],
                 document_id=e['document_id'], page_id=e['page_id'],
                 page_number=e['page_number'], start_offset=e['start_offset'],
                 end_offset=e['end_offset'], matched_text=e['matched_text'],
                 verification_status=e['status']))
    return result


def execute_matching_run(run_id: str, db: Session, *, page_size: int = 50) -> str:
    """Checkpoint after every page; existing application results are never duplicated."""
    run = db.scalar(select(MatchingRun).where(MatchingRun.id == run_id).with_for_update())
    if run is None:
        return 'missing'
    if run.status == 'completed':
        return 'unchanged'
    run.status = 'running'
    run.error_code = None
    db.commit()
    mapped = run.skill_mapping_snapshot
    offset = 0
    while offset < len(run.application_ids_snapshot):
        ids = run.application_ids_snapshot[offset: offset + page_size]
        applications = db.scalars(select(Application).where(
            Application.organization_id == run.organization_id,
            Application.campaign_id == run.campaign_id,
            Application.id.in_(ids)).order_by(Application.id)).all()
        for app in applications:
            exists = db.scalar(select(MatchingResult.id).where(
                MatchingResult.run_id == run.id, MatchingResult.application_id == app.id))
            if not exists:
                calculate_application(db, run, app, mapped)
        db.flush()
        run.processed = db.scalar(select(func.count()).select_from(MatchingResult).where(
            MatchingResult.run_id == run.id)) or 0
        db.commit()
        offset += len(ids)
    run.processed = db.scalar(select(func.count()).select_from(MatchingResult).where(
        MatchingResult.run_id == run.id)) or 0
    run.status = 'completed'
    run.completed_at = utcnow()
    db.commit()
    return 'completed'


def is_result_stale(db: Session, run: MatchingRun, result: MatchingResult) -> bool:
    """Any changed document/mention makes the saved result stale, never silently fresh."""
    app = db.scalar(select(Application).where(Application.id == result.application_id,
               Application.organization_id == run.organization_id,
               Application.campaign_id == run.campaign_id))
    if app is None:
        return True
    ready, review, doc_fp, evidences = applicant_inputs(db, run, app)
    current = calculate(run.requirements_snapshot, run.weights_snapshot, evidences,
                        run.skill_mapping_snapshot,
                        documents_ready=ready, document_fingerprint=doc_fp)
    return current.fingerprint != result.evidence_fingerprint
