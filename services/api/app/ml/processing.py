"""Idempotent NLP extraction from already persisted document pages.

Never assumes an unobserved skill is absent. Evidence never includes inferred proficiency.
"""
from hashlib import sha256
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.ml.recognition import RULES_VERSION, extract_mentions, normalize
from app.ml.sections import extract_source_facts, SECTIONS_VERSION
from app.models import CVDocument, DocumentPage, DocumentNlpRun, SkillEvidence, Skill, SkillAlias, OrganizationSkillAlias, DocumentFact
from app.models.auth import utcnow


def analyze_document(document_id: str, db: Session) -> str:
    doc = db.scalar(select(CVDocument).where(CVDocument.id == document_id).with_for_update())
    if doc is None:
        return 'missing'
    if doc.status not in ('completed', 'needs_review'):
        return 'not_extracted'
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc.id)
                       .order_by(DocumentPage.page_number)).all()
    references = db.execute(select(Skill, SkillAlias).join(SkillAlias, SkillAlias.skill_id == Skill.id)
                            .where(Skill.active.is_(True), SkillAlias.verified.is_(True))).all()
    aliases = [(skill.id, alias.normalized_alias, normalize(skill.label_fr),
                       normalize(skill.label_en), skill.code, skill.version)
                      for skill, alias in references]
    local = db.execute(select(Skill, OrganizationSkillAlias).join(OrganizationSkillAlias,
                 OrganizationSkillAlias.skill_id == Skill.id).where(
                 Skill.active.is_(True), OrganizationSkillAlias.organization_id == doc.organization_id)).all()
    aliases += [(skill.id, alias.normalized_alias, normalize(skill.label_fr),
                 normalize(skill.label_en), skill.code, f'org-{alias.version}') for skill,alias in local]
    aliases.sort()
    fingerprint = sha256(repr(aliases).encode('utf-8')).hexdigest()
    datahash = sha256(repr([(p.id, p.text, p.version) for p in pages]).encode('utf-8')).hexdigest()
    run = db.scalar(select(DocumentNlpRun).where(DocumentNlpRun.document_id == doc.id).with_for_update())
    if run and run.status == 'completed' and run.rules_version == RULES_VERSION and \
       run.taxonomy_fingerprint == fingerprint and run.content_fingerprint == datahash:
        return 'unchanged'
    if run is None:
        run = DocumentNlpRun(organization_id=doc.organization_id, document_id=doc.id,
                             status='processing', rules_version=RULES_VERSION,
                             taxonomy_fingerprint=fingerprint, content_fingerprint=datahash)
        db.add(run)
    else:
        run.status = 'processing'; run.rules_version = RULES_VERSION
        run.taxonomy_fingerprint = fingerprint; run.content_fingerprint = datahash
    try:
        # Retain confirmed or rejected human reviews on unchanged exact evidence spans.
        existing = db.scalars(select(SkillEvidence).where(SkillEvidence.document_id == doc.id)).all()
        human = {(e.page_id, e.start_offset, e.end_offset, e.skill_id):
                 (e.status,e.reviewed_by,e.reviewed_at) for e in existing
                 if e.status in ('confirmed', 'rejected')}
        db.execute(delete(SkillEvidence).where(SkillEvidence.document_id == doc.id))
        db.execute(delete(DocumentFact).where(DocumentFact.document_id == doc.id))
        dictionary = [(skill, alias, fr if alias == fr else en)
                      for skill, alias, fr, en, code, version in aliases]
        for page in pages:
            for mention in extract_mentions(page.text, dictionary):
                key = (page.id, mention.start, mention.end, mention.skill_id)
                review = human.get(key)
                db.add(SkillEvidence(organization_id=doc.organization_id, document_id=doc.id,
                                     page_id=page.id, skill_id=mention.skill_id,
                                     start_offset=mention.start, end_offset=mention.end,
                                     matched_text=mention.mention, match_method=mention.method,
                                     status=review[0] if review else mention.status, rules_version=RULES_VERSION,
                                     context_code=mention.context_code,
                                     reviewed_by=review[1] if review else None,
                                     reviewed_at=review[2] if review else None))
            for line in extract_source_facts(page.text):
                db.add(DocumentFact(organization_id=doc.organization_id, document_id=doc.id,
                    page_id=page.id, category=line.section, start_offset=line.start,
                    end_offset=line.end, source_text=line.text, rule_version=SECTIONS_VERSION,
                    review_status='unverified'))
        run.status = 'completed'; run.error_code = None; run.processed_at = utcnow()
        db.commit()
        return 'completed'
    except Exception:
        db.rollback()
        run = db.scalar(select(DocumentNlpRun).where(DocumentNlpRun.document_id == doc.id))
        if run:
            run.status = 'failed'; run.error_code = 'NLP_PROCESSING_FAILED'; db.commit()
        return 'failed'
