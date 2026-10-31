"""Tenant-scoped read access to source-anchored mentions. No automated decisions."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import Principal
from app.core.permissions import require_role
from app.api.v1.documents import scoped_document
from app.models import Skill, SkillEvidence, DocumentPage, DocumentNlpRun, DocumentFact
from app.models.auth import utcnow
from app.services.audit import record

router = APIRouter()

@router.get('/skills')
def list_skills(q: str = Query('',max_length=100), limit: int = Query(50,ge=1,le=100),
                actor: Principal = Depends(require_role('org_admin','recruiter','evaluator')),
                db: Session = Depends(get_db)):
    stmt=select(Skill).where(Skill.active.is_(True))
    if q:
        safe = q.replace('%','\\%').replace('_','\\_')
        stmt=stmt.where(Skill.label_fr.ilike(f'%{safe}%',escape='\\') |
                        Skill.label_en.ilike(f'%{safe}%',escape='\\') |
                        Skill.code.ilike(f'%{safe}%',escape='\\'))
    rows=db.scalars(stmt.order_by(Skill.code).limit(limit)).all()
    return {'items':[{'id':s.id,'code':s.code,'label_fr':s.label_fr,'label_en':s.label_en,
                      'taxonomy':s.taxonomy,'version':s.version,'external_uri':s.external_uri} for s in rows]}

class SemanticSkillIn(BaseModel):
    text: str
    limit: int = 8

@router.post('/skills/semantic-suggestions')
def skill_semantic_suggestions(body: SemanticSkillIn,
    actor: Principal = Depends(require_role('org_admin','recruiter')),
    db: Session = Depends(get_db)):
    """Optional retrieval by LABEL similarity, never auto-activates an alias or criterion."""
    from app.core.config import get_settings
    from app.ml.remote import ml_request
    if not get_settings().semantic_enabled:
        raise HTTPException(503, 'Recherche sémantique non activée')
    if not 2 <= len(body.text.strip()) <= 250 or not 1 <= body.limit <= 20:
        raise HTTPException(422, 'Requête ou limite invalide')
    # Explicitly bounded catalogue; deterministic ordering and active references only.
    catalogue = db.scalars(select(Skill).where(Skill.active.is_(True))
             .order_by(Skill.code).limit(120)).all()
    if not catalogue:
        return {'items': [], 'note': 'Aucun référentiel actif disponible'}
    ids = {skill.id: skill for skill in catalogue}
    try:
        raw = ml_request('/private/rank-skills', {
            'query': body.text.strip(), 'limit': body.limit,
            'labels': [{'skill_id': s.id, 'label': f'{s.label_fr} / {s.label_en}'} for s in catalogue]})
    except Exception:
        raise HTTPException(503, 'Modèle sémantique local indisponible') from None
    items = []
    for item in raw.get('items', []):
        skill = ids.get(item.get('skill_id'))
        score = item.get('similarity')
        if not skill or not isinstance(score, (int, float)) or not -1 <= score <= 1:
            continue
        items.append({'skill_id': skill.id, 'code': skill.code, 'label': skill.label_fr,
                      'similarity': float(score), 'status': 'candidate_to_review'})
    record(db, actor, 'nlp.skill_suggestions.viewed', 'organization', actor.organization.id,
           {'returned': len(items)})
    db.commit()
    return {'items': items, 'model': get_settings().embedding_model,
            'note': 'Similarité brute de libellés, pas une compétence détectée ou équivalente.'}


@router.get('/documents/{doc_id}/nlp')
def document_nlp(doc_id: str,
                 actor: Principal = Depends(require_role('org_admin','recruiter')),
                 db: Session = Depends(get_db)):
    doc=scoped_document(doc_id,actor,db)
    run=db.scalar(select(DocumentNlpRun).where(DocumentNlpRun.document_id==doc.id))
    mentions=db.execute(select(SkillEvidence,Skill,DocumentPage)
        .join(Skill,Skill.id==SkillEvidence.skill_id)
        .join(DocumentPage,DocumentPage.id==SkillEvidence.page_id)
        .where(SkillEvidence.organization_id==actor.organization.id, SkillEvidence.document_id==doc.id)
        .order_by(DocumentPage.page_number,SkillEvidence.start_offset)).all()
    record(db,actor,'document.nlp.viewed','document',doc.id)
    db.commit()
    items=[]
    for evidence,skill,page in mentions:
        # Verify offsets still correspond to the source; no hallucinated snippets.
        if page.text[evidence.start_offset:evidence.end_offset] != evidence.matched_text:
            continue
        items.append({'id':evidence.id,'skill_id':skill.id,'skill_code':skill.code,
                      'skill_label':skill.label_fr, 'status':evidence.status,
                      'method':evidence.match_method,'page_number':page.page_number,
                      'start_offset':evidence.start_offset,'end_offset':evidence.end_offset,
                      'source_quote':page.text[max(0,evidence.start_offset-90):min(len(page.text),evidence.end_offset+90)],
                      'matched_text':evidence.matched_text,'rules_version':evidence.rules_version, 'context_code':evidence.context_code})
    return {'document_id':doc.id,'state':run.status if run else 'not_started',
            'rules_version':run.rules_version if run else None,
            'items':items,'note':'Mentions du document, pas une validation de maîtrise professionnelle.'}

@router.get('/documents/{doc_id}/nlp/facts')
def document_facts(doc_id: str, actor: Principal = Depends(require_role('org_admin','recruiter')),
                   db: Session = Depends(get_db)):
    """Section-grounded literal extracts. Never interpreted as a confirmed diploma or job."""
    doc = scoped_document(doc_id, actor, db)
    facts = db.execute(select(DocumentFact, DocumentPage).join(
        DocumentPage, DocumentPage.id == DocumentFact.page_id).where(
        DocumentFact.organization_id == actor.organization.id,
        DocumentFact.document_id == doc.id,
        DocumentPage.document_id == doc.id).order_by(
        DocumentPage.page_number, DocumentFact.start_offset)).all()
    items = [{'id': f.id, 'category': f.category, 'page_number': page.page_number,
              'start_offset': f.start_offset, 'end_offset': f.end_offset,
              'source_text': f.source_text, 'review_status': f.review_status,
              'rule_version': f.rule_version}
             for f, page in facts
             if 0 <= f.start_offset < f.end_offset <= len(page.text)
             and page.text[f.start_offset:f.end_offset] == f.source_text]
    record(db, actor, 'document.nlp.facts.viewed', 'document', doc.id, {'count': len(items)})
    db.commit()
    return {'document_id': doc.id, 'items': items,
            'note': 'Lignes originales à examiner : aucune durée, qualification ou niveau déduit.'}


class ReviewIn(BaseModel):
    decision: str

@router.patch('/documents/{doc_id}/nlp/{mention_id}/review')
def review_mention(doc_id: str,mention_id: str,body:ReviewIn,
                 actor: Principal = Depends(require_role('org_admin','recruiter')),
                 db: Session = Depends(get_db)):
    doc=scoped_document(doc_id,actor,db)
    if body.decision not in ('confirmed','rejected','needs_review'):
        raise HTTPException(422,'Décision non reconnue')
    mention=db.scalar(select(SkillEvidence).where(SkillEvidence.id==mention_id,
         SkillEvidence.document_id==doc.id,SkillEvidence.organization_id==actor.organization.id))
    if mention is None: raise HTTPException(404,'Mention introuvable')
    mention.status=body.decision
    mention.reviewed_by=actor.user.id
    mention.reviewed_at=utcnow()
    record(db,actor,'nlp.mention.reviewed','skill_evidence',mention.id,
           {'decision':body.decision,'document_id':doc.id})
    db.commit()
    return {'id':mention.id,'status':mention.status}

@router.post('/documents/{doc_id}/nlp/analyze',status_code=202)
def queue_analysis(doc_id: str,
                   actor: Principal = Depends(require_role('org_admin','recruiter')),
                   db: Session = Depends(get_db)):
    doc=scoped_document(doc_id,actor,db)
    if doc.status not in ('completed','needs_review'):
        raise HTTPException(409,'Extraction documentaire non terminée')
    try:
        from app.workers.tasks import nlp_task
        queued=nlp_task.delay(doc.id)
    except Exception:
        raise HTTPException(503,'File de traitement NLP indisponible') from None
    return {'document_id':doc.id,'queued':True,'task_id':queued.id}

class AliasIn(BaseModel):
    alias: str
    justification: str
    language: str = 'und'

@router.get('/skills/{skill_id}/aliases')
def skill_aliases(skill_id: str,
                  actor: Principal=Depends(require_role('org_admin','recruiter')),
                  db:Session=Depends(get_db)):
    from app.models import SkillAlias, OrganizationSkillAlias
    if not db.get(Skill,skill_id): raise HTTPException(404,'Compétence introuvable')
    official=db.scalars(select(SkillAlias).where(SkillAlias.skill_id==skill_id,
                                                SkillAlias.verified.is_(True))).all()
    local=db.scalars(select(OrganizationSkillAlias).where(OrganizationSkillAlias.skill_id==skill_id,
                          OrganizationSkillAlias.organization_id==actor.organization.id)).all()
    return {'items':[{'id':a.id,'alias':a.normalized_alias,'source':a.provenance} for a in official]+
                    [{'id':a.id,'alias':a.normalized_alias,'source':'organization',
                      'justification':a.justification} for a in local]}

@router.post('/skills/{skill_id}/aliases',status_code=201)
def add_org_alias(skill_id: str,body:AliasIn,
                  actor: Principal=Depends(require_role('org_admin')),
                  db:Session=Depends(get_db)):
    from app.models import OrganizationSkillAlias
    from app.ml.recognition import normalize
    from sqlalchemy.exc import IntegrityError
    skill=db.get(Skill,skill_id)
    if not skill or not skill.active: raise HTTPException(404,'Compétence introuvable')
    alias=normalize(body.alias)
    if not 2<=len(alias)<=190 or not 8<=len(body.justification.strip())<=400:
        raise HTTPException(422,'Alias ou justification invalide')
    if body.language not in ('fr','en','und'): raise HTTPException(422,'Langue non reconnue')
    entry=OrganizationSkillAlias(organization_id=actor.organization.id,skill_id=skill.id,
           normalized_alias=alias,language=body.language,justification=body.justification.strip(),
           reviewed_by=actor.user.id,reviewed_at=utcnow(),version=1)
    db.add(entry)
    try:
        db.flush()
        record(db,actor,'skill.alias.added','skill',skill.id,{'alias':alias})
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Alias déjà présent dans cette organisation') from None
    return {'id':entry.id,'alias':alias,'source':'organization'}
