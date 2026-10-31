"""Africa Skills Intelligence modules. Distinct from autonomous recruitment matching."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Skill, SkillRelation, CVDocument, DocumentPage, SkillEvidence,
                        Application, MatchingResult, MatchingRun, MatchingCriterionResult,
                        TrainingCourse, OpportunityPreference, Candidate)
from app.models.auth import utcnow
from app.services.audit import record
from app.api.v1.documents import scoped_document
from app.ml.africa_evaluation import run_benchmark
from app.ml.fairrank import identity_invariance

router=APIRouter(prefix='/africa')

class RelationIn(BaseModel):
    source_skill_id:str=Field(min_length=36,max_length=36)
    target_skill_id:str=Field(min_length=36,max_length=36)
    relation_type:str=Field(pattern='^(equivalent|related|prerequisite)$')
    justification:str=Field(min_length=15,max_length=2000)
    source_reference:HttpUrl
    country_code:str=Field(default='CD',pattern='^(CD|RW|BI|KE|UG)$')

def relation_out(r,source,target):
    return {'id':r.id,'source_skill_id':source.id,'source':source.label_fr,'target_skill_id':target.id,
            'target':target.label_fr,'relation_type':r.relation_type,'country_code':r.country_code,
            'justification':r.justification,'source_reference':r.source_reference,'version':r.version,
            'verified_at':r.verified_at,'verification':'organization_admin_curated',
            'effect_on_matching':'none_without_independent_documentary_evidence'}

@router.get('/talentgraph/relations')
def relations(skill_id:str|None=None,limit:int=Query(60,ge=1,le=100),
              actor:Principal=Depends(require_role('org_admin','recruiter')),
              db:Session=Depends(get_db)):
    stmt=select(SkillRelation,Skill).join(Skill,Skill.id==SkillRelation.source_skill_id).where(
        SkillRelation.organization_id==actor.organization.id)
    if skill_id:
        stmt=stmt.where((SkillRelation.source_skill_id==skill_id)|(SkillRelation.target_skill_id==skill_id))
    found=db.execute(stmt.order_by(SkillRelation.verified_at.desc()).limit(limit)).all()
    target_ids={r.target_skill_id for r,_ in found}
    targets={x.id:x for x in db.scalars(select(Skill).where(Skill.id.in_(target_ids))).all()} if target_ids else {}
    return {'items':[relation_out(r,s,targets[r.target_skill_id]) for r,s in found if r.target_skill_id in targets],
            'note':'Relations validées dans votre organisation. Proximité ≠ équivalence; aucun crédit automatique au candidat.'}

@router.post('/talentgraph/relations',status_code=201)
def create_relation(body:RelationIn,
    actor:Principal=Depends(require_role('org_admin')),db:Session=Depends(get_db)):
    if body.source_skill_id==body.target_skill_id:raise HTTPException(422,'Une compétence ne peut pas être reliée à elle-même')
    if body.source_reference.scheme != 'https' or len(str(body.source_reference))>500:
        raise HTTPException(422,'Une référence HTTPS de 500 caractères maximum est obligatoire')
    skills=db.scalars(select(Skill).where(Skill.id.in_([body.source_skill_id,body.target_skill_id]),Skill.active.is_(True))).all()
    if len(skills)!=2:raise HTTPException(422,'Compétences actives inconnues')
    row=SkillRelation(organization_id=actor.organization.id,source_skill_id=body.source_skill_id,
        target_skill_id=body.target_skill_id,relation_type=body.relation_type,
        source_reference=str(body.source_reference),country_code=body.country_code,
        justification=body.justification.strip(),reviewed_by=actor.user.id,version=1)
    db.add(row)
    try:
        db.flush();record(db,actor,'africa.graph_relation.created','skill_relation',row.id,
            {'kind':row.relation_type,'country':row.country_code});db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Relation déjà enregistrée') from None
    by_id={s.id:s for s in skills}
    return relation_out(row,by_id[body.source_skill_id],by_id[body.target_skill_id])

@router.delete('/talentgraph/relations/{relation_id}')
def remove_relation(relation_id:str,actor:Principal=Depends(require_role('org_admin')),
                    db:Session=Depends(get_db)):
    row=db.scalar(select(SkillRelation).where(SkillRelation.id==relation_id,
        SkillRelation.organization_id==actor.organization.id))
    if not row:raise HTTPException(404,'Relation introuvable')
    record(db,actor,'africa.graph_relation.deleted','skill_relation',row.id)
    db.delete(row);db.commit()
    return {'deleted':True}

@router.get('/skillsproof/documents/{document_id}')
def skillsproof(document_id:str,actor:Principal=Depends(require_role('org_admin','recruiter')),
                db:Session=Depends(get_db)):
    doc=scoped_document(document_id,actor,db)
    rows=db.execute(select(SkillEvidence,DocumentPage,Skill)
        .join(DocumentPage,(DocumentPage.id==SkillEvidence.page_id)&(DocumentPage.document_id==document_id))
        .join(Skill,Skill.id==SkillEvidence.skill_id)
        .where(SkillEvidence.organization_id==actor.organization.id,
               SkillEvidence.document_id==document_id)
        .order_by(DocumentPage.page_number,SkillEvidence.start_offset).limit(300)).all()
    output=[]
    for e,p,s in rows:
        if not(0<=e.start_offset<e.end_offset<=len(p.text) and p.text[e.start_offset:e.end_offset]==e.matched_text):continue
        status=('human_confirmed' if e.status=='confirmed' else 'human_rejected' if e.status=='rejected'
                else 'requires_review' if e.status=='needs_review' else 'direct_mention_not_skill_level')
        output.append({'evidence_id':e.id,'skill_id':s.id,'skill':s.label_fr,'status':status,
                       'page_number':p.page_number,'start_offset':e.start_offset,'end_offset':e.end_offset,
                       'text':p.text[max(0,e.start_offset-90):min(len(p.text),e.end_offset+90)],
                       'matched_text':e.matched_text,'method':e.match_method,'rules_version':e.rules_version})
    record(db,actor,'africa.skillsproof.viewed','document',document_id);db.commit()
    return {'document_id':doc.id,'items':output,'note':'Preuves littérales, jamais une qualification ou expertise inférée.'}

@router.get('/prooflab/benchmark')
def prooflab(actor:Principal=Depends(require_role('org_admin','recruiter'))):
    return run_benchmark()

class InvarianceIn(BaseModel):
    professional_text:str=Field(min_length=5,max_length=4000)
    synthetic_identity_labels:list[str]=Field(min_length=2,max_length=8)

@router.post('/fairrank/identity-check')
def fairrank_check(body:InvarianceIn,
                   actor:Principal=Depends(require_role('org_admin')),
                   db:Session=Depends(get_db)):
    # Labels are discarded and never used to build candidate features.
    from app.models import SkillAlias
    from app.ml.recognition import normalize
    aliases=db.execute(select(SkillAlias.skill_id,SkillAlias.normalized_alias,Skill.label_fr)
        .join(Skill,Skill.id==SkillAlias.skill_id)
        .where(SkillAlias.verified.is_(True),Skill.active.is_(True)).limit(500)).all()
    prepared=[(s,normalize(a),normalize(c)) for s,a,c in aliases]
    try:
        return identity_invariance(body.professional_text,body.synthetic_identity_labels,prepared)
    except ValueError:
        raise HTTPException(422,'Variantes fictives invalides') from None

@router.get('/multilingual/status')
def multilingual(actor:Principal=Depends(require_role('org_admin','recruiter'))):
    return {'languages':[{'code':'fr','status':'lexical_supported_unvalidated_on_real_corpus'},
                         {'code':'en','status':'lexical_supported_unvalidated_on_real_corpus'},
                         {'code':'sw','status':'experimental_not_enabled_for_matching'}],
            'note':'Les langues ne sont pas déclarées scientifiquement validées; l’analyse swahili reste expérimentale.'}

class ConsentIn(BaseModel):
    state:str=Field(pattern='^(opt_in_recorded|withdrawn)$')
    evidence_reference:str=Field(min_length=8,max_length=250)

@router.put('/opportunities/candidates/{candidate_id}/preference')
def preference(candidate_id:str,body:ConsentIn,
               actor:Principal=Depends(require_role('org_admin')),
               db:Session=Depends(get_db)):
    candidate=db.scalar(select(Candidate).where(Candidate.id==candidate_id,Candidate.organization_id==actor.organization.id))
    if not candidate:raise HTTPException(404,'Candidat introuvable')
    row=db.scalar(select(OpportunityPreference).where(OpportunityPreference.organization_id==actor.organization.id,
                                                       OpportunityPreference.candidate_id==candidate_id))
    if row is None:
        row=OpportunityPreference(organization_id=actor.organization.id,candidate_id=candidate_id,updated_by=actor.user.id)
        db.add(row)
    row.consent_state=body.state;row.evidence_reference=body.evidence_reference.strip()
    row.updated_by=actor.user.id;row.updated_at=utcnow()
    db.flush();record(db,actor,'africa.opportunity_preference.recorded','candidate',candidate_id,
                      {'state':body.state});db.commit()
    return {'candidate_id':candidate_id,'recorded_state':row.consent_state,
            'warning':'Déclaration administrative, non preuve indépendante du consentement; aucune transmission automatique.'}

@router.get('/opportunities/matching-results/{result_id}')
def opportunities(result_id:str,actor:Principal=Depends(require_role('org_admin','recruiter')),
                  db:Session=Depends(get_db)):
    found=db.execute(select(MatchingResult,MatchingRun).join(MatchingRun,MatchingRun.id==MatchingResult.run_id)
        .where(MatchingResult.id==result_id,MatchingRun.organization_id==actor.organization.id)).first()
    if not found:raise HTTPException(404,'Analyse introuvable')
    result,run=found
    # An administrator-entered preference is not consent. Only a verified candidate's
    # self-service consent event can enable personalised training suggestions.
    from app.api.v1.candidate_portal import current_consent
    if not current_consent(db, result.candidate_id, actor.organization.id):
        return {'status':'consent_not_recorded','items':[],
                'note':'Aucun parcours individualisé affiché sans indication de consentement enregistrée.'}
    rows=db.scalars(select(MatchingCriterionResult).where(MatchingCriterionResult.result_id==result.id,
                    MatchingCriterionResult.state.in_(['not_documented','needs_review','manual_review_required'])).limit(80)).all()
    skills={str(run.skill_mapping_snapshot.get(r.requirement_id)) for r in rows if run.skill_mapping_snapshot.get(r.requirement_id)}
    if not skills:
        return {'status':'no_verifiable_skill_links','items':[]}
    courses=db.scalars(select(TrainingCourse).where(TrainingCourse.organization_id==actor.organization.id,
        TrainingCourse.skill_id.in_(skills),TrainingCourse.is_active.is_(True),TrainingCourse.verified_at.is_not(None)).limit(50)).all()
    return {'status':'human_review_preview_only','items':[{'title':c.title,'provider':c.provider,
            'official_url':c.official_url,'language':c.language,'level':c.level,'skill_id':c.skill_id,
            'source_verified_at':c.verified_at} for c in courses],
            'note':'Formation réelle vérifiée par un humain. Non retrouvé sur CV ≠ compétence manquante. Aucun envoi automatique.'}
