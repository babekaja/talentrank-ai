"""Phase 5: review-supporting matching endpoints, never decision automation."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Job, RecruitmentCampaign, Application, ApplicationReview,
                        MatchingConfiguration, MatchingRun, MatchingResult,
                        MatchingCriterionResult, MatchingEvidence, DocumentPage)
from app.ml.matching import ALGORITHM_VERSION, DEFAULT_WEIGHTS
from app.ml.matching_service import requirement_snapshot, resolve_skills, is_result_stale
from app.ml.documentary_ranking import ranked_results
from app.services.audit import record

router = APIRouter()


def enqueue_matching(run_id: str) -> None:
    from app.workers.tasks import matching_task
    matching_task.delay(run_id)


class WeightsIn(BaseModel):
    essential: int = Field(ge=0, le=100)
    desirable: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    projects_training: int = Field(ge=0, le=100)

    @model_validator(mode='after')
    def valid_weights(self):
        if sum(self.model_dump().values()) != 100 or self.essential == 0:
            raise ValueError('Somme des poids = 100 et catégorie essentielle non nulle')
        return self


def last_config(db: Session, organization_id: str):
    return db.scalar(select(MatchingConfiguration).where(
        MatchingConfiguration.organization_id == organization_id)
        .order_by(MatchingConfiguration.version.desc()).limit(1))


@router.get('/matching/configuration')
def matching_config(actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                    db: Session = Depends(get_db)):
    row = last_config(db, actor.organization.id)
    return {'version': row.version if row else 0,
            'weights': row.weights if row else DEFAULT_WEIGHTS,
            'algorithm_version': ALGORITHM_VERSION}


@router.post('/matching/configuration', status_code=201)
def update_matching_config(body: WeightsIn,
             actor: Principal = Depends(require_role('org_admin')),
             db: Session = Depends(get_db)):
    from app.models import Organization
    db.scalar(select(Organization).where(Organization.id == actor.organization.id).with_for_update())
    row = last_config(db, actor.organization.id)
    new = MatchingConfiguration(organization_id=actor.organization.id,
          version=(row.version + 1) if row else 1,
          weights=body.model_dump(), created_by=actor.user.id)
    db.add(new)
    db.flush()
    record(db, actor, 'matching.configuration.created', 'matching_config', new.id,
           {'version': new.version, 'weights': new.weights})
    db.commit()
    return {'version': new.version, 'weights': new.weights, 'algorithm_version': ALGORITHM_VERSION}


def run_or_404(db: Session, actor: Principal, run_id: str):
    row = db.scalar(select(MatchingRun).where(MatchingRun.id == run_id,
        MatchingRun.organization_id == actor.organization.id))
    if row is None:
        raise HTTPException(404, 'Analyse introuvable')
    return row


def run_info(row: MatchingRun):
    requirements = row.requirements_snapshot or []
    mapping = row.skill_mapping_snapshot or {}
    skills = [item for item in requirements if item.get('category') == 'skill']
    mapped = [item for item in skills if mapping.get(item.get('id'))]
    return {'id': row.id, 'campaign_id': row.campaign_id, 'job_id': row.job_id,
            'status': row.status, 'total': row.total, 'processed': row.processed,
            'criteria_version': row.criteria_version, 'config_version': row.config_version,
            'algorithm_version': row.algorithm_version, 'weights': row.weights_snapshot,
            'mapping': {'skill_criteria': len(skills), 'mapped': len(mapped),
                        'unmapped': len(skills) - len(mapped),
                        'mapped_required': sum(bool(item.get('required')) for item in mapped)},
            'created_at': row.created_at, 'completed_at': row.completed_at,
            'note': 'Couverture documentaire, non une probabilité d’embauche.'}


@router.post('/jobs/{job_id}/matching-runs', status_code=202)
def start_matching(job_id: str, campaign_id: str = Query(...),
                   actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                   db: Session = Depends(get_db)):
    job = db.scalar(select(Job).options(selectinload(Job.requirements)).where(
          Job.id == job_id, Job.organization_id == actor.organization.id).with_for_update())
    if not job:
        raise HTTPException(404, 'Offre introuvable')
    campaign = db.scalar(select(RecruitmentCampaign).where(
          RecruitmentCampaign.id == campaign_id, RecruitmentCampaign.organization_id == actor.organization.id,
          RecruitmentCampaign.job_id == job.id))
    if not campaign:
        raise HTTPException(404, 'Campagne introuvable pour cette offre')
    if not job.criteria_confirmed_at or not job.requirements:
        raise HTTPException(409, 'Critères non confirmés')
    active = db.scalar(select(MatchingRun.id).where(MatchingRun.organization_id == actor.organization.id,
          MatchingRun.campaign_id == campaign.id, MatchingRun.status.in_(['queued','running'])).limit(1))
    if active:
        raise HTTPException(409, 'Une analyse est déjà en cours pour cette campagne')
    config = last_config(db, actor.organization.id)
    application_ids = sorted(db.scalars(select(Application.id).where(
          Application.organization_id == actor.organization.id,
          Application.campaign_id == campaign.id)).all())
    total = len(application_ids)
    if not total:
        raise HTTPException(409, 'La campagne ne contient aucune candidature')
    requirements = requirement_snapshot(job)
    mapping = resolve_skills(db, requirements)
    skill_requirements = [item for item in requirements if item['category'] == 'skill']
    mapped_skills = [item for item in skill_requirements if mapping.get(item['id'])]
    mapped_required = [item for item in mapped_skills if item['required']]
    if not skill_requirements:
        raise HTTPException(409, 'Aucun critère de compétence : le matching documentaire ne peut pas être lancé')
    if not mapped_skills:
        raise HTTPException(409, 'Aucun critère n’est relié au référentiel de compétences')
    if any(item['required'] for item in skill_requirements) and not mapped_required:
        raise HTTPException(409, 'Aucun critère essentiel n’est relié au référentiel de compétences')
    run = MatchingRun(organization_id=actor.organization.id, campaign_id=campaign.id,
          job_id=job.id, criteria_version=job.criteria_version,
          config_version=config.version if config else 0,
          algorithm_version=ALGORITHM_VERSION,
          weights_snapshot=dict(config.weights if config else DEFAULT_WEIGHTS),
          requirements_snapshot=requirements, application_ids_snapshot=application_ids,
          skill_mapping_snapshot=mapping,
          total=total, created_by=actor.user.id)
    db.add(run)
    db.flush()
    record(db, actor, 'matching.run.requested', 'matching_run', run.id,
           {'campaign_id':campaign.id, 'total':total})
    db.commit()
    try:
        enqueue_matching(run.id)
    except Exception:
        run.status = 'failed'
        run.error_code = 'QUEUE_UNAVAILABLE'
        db.commit()
        raise HTTPException(503, 'File de calcul indisponible ; analyse non lancée') from None
    return run_info(run)


@router.get('/matching-runs/{run_id}')
def get_run(run_id: str, actor: Principal = Depends(require_role('org_admin','recruiter')),
            db: Session = Depends(get_db)):
    return run_info(run_or_404(db, actor, run_id))


@router.get('/matching-runs')
def list_runs(campaign_id: str | None = None, limit: int = Query(30,ge=1,le=100),
              actor: Principal = Depends(require_role('org_admin','recruiter')),
              db: Session = Depends(get_db)):
    q = select(MatchingRun).where(MatchingRun.organization_id == actor.organization.id)
    if campaign_id:
        q = q.where(MatchingRun.campaign_id == campaign_id)
    return {'items': [run_info(r) for r in db.scalars(q.order_by(MatchingRun.created_at.desc(), MatchingRun.id.desc())
                                                        .limit(limit)).all()]}


def result_or_404(db, actor, result_id):
    row = db.execute(select(MatchingResult, MatchingRun).join(
        MatchingRun, MatchingRun.id == MatchingResult.run_id).where(
        MatchingResult.id == result_id, MatchingRun.organization_id == actor.organization.id)).first()
    if not row:
        raise HTTPException(404, 'Résultat introuvable')
    return row


def result_info(row: MatchingResult):
    return {'id':row.id, 'application_id':row.application_id,
            'candidate_reference_id':row.candidate_id,
            'score':float(row.score) if row.score is not None and row.state == 'documentary_coverage' else None,
            'state':row.state,'documented':row.documented,'to_review':row.to_review,
            'not_documented':row.not_documented, 'group_coverage':row.group_coverage,
            'score_note':('Analyse partielle : certaines exigences doivent être examinées par une personne.'
                          if row.state == 'partial_review_required' else
                          'Score documentaire, pas une probabilité ni une décision de recrutement.')}


@router.get('/matching-runs/{run_id}/results')
def list_results(run_id: str, limit: int = Query(30,ge=1,le=100), offset: int = Query(0,ge=0),
                 actor: Principal = Depends(require_role('org_admin','recruiter')),
                 db: Session = Depends(get_db)):
    run=run_or_404(db,actor,run_id)
    rows,ranking=ranked_results(db,run)
    return {'items':[{**result_info(result),**rank} for result,rank in rows[offset:offset+limit]],
            'total':len(rows),'limit':limit,'offset':offset,'ranking':ranking,
            'note':ranking['note']}


@router.get('/matching-results/{result_id}/explanation')
def explain(result_id: str,
            actor: Principal = Depends(require_role('org_admin','recruiter')),
            db: Session = Depends(get_db)):
    result, run = result_or_404(db,actor,result_id)
    ranked,ranking=ranked_results(db,run)
    rank=next((rank for item,rank in ranked if item.id==result.id),{})
    criteria=db.scalars(select(MatchingCriterionResult).where(
                MatchingCriterionResult.result_id==result.id).order_by(MatchingCriterionResult.code)).all()
    proofs=db.execute(select(MatchingEvidence,MatchingCriterionResult.id).join(
             MatchingCriterionResult, MatchingCriterionResult.id == MatchingEvidence.criterion_result_id)
             .where(MatchingCriterionResult.result_id==result.id)).all()
    linked={criterion_id:proof for proof,criterion_id in proofs}
    items=[]
    for c in criteria:
        proof=linked.get(c.id)
        evidence=None
        if proof:
            page=db.get(DocumentPage,proof.page_id)
            valid=bool(page and page.text[proof.start_offset:proof.end_offset]==proof.matched_text)
            evidence={'document_id':proof.document_id,'page_number':proof.page_number,
                      'matched_text':proof.matched_text,'start_offset':proof.start_offset,
                      'end_offset':proof.end_offset,'source_still_matches':valid,
                      'source_excerpt':page.text[max(0,proof.start_offset-85):min(len(page.text),proof.end_offset+85)] if valid else None,
                      'verification_status_at_run':proof.verification_status}
        items.append({'code':c.code,'label':c.label,'group':c.group_code,'state':c.state,
                      'weight':c.weight,'contribution':float(c.contribution),
                      'note_code':c.note_code,'evidence':evidence})
    record(db,actor,'matching.explanation.viewed','matching_result',result.id)
    db.commit()
    return {**result_info(result),**rank,'ranking':ranking,'run_id':run.id, 'criteria_version':run.criteria_version,
            'algorithm_version':run.algorithm_version, 'configuration_version':run.config_version,
            'stale':is_result_stale(db,run,result), 'criteria':items,
            'disclaimer':'Mentions documentaires seulement. Si un critère reste non évalué, aucun score global /100 n’est publié. Une absence de mention ne prouve pas une absence de compétence.'}


class CompareIn(BaseModel):
    result_ids: list[str] = Field(min_length=2,max_length=5)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.result_ids))!=len(self.result_ids):
            raise ValueError('Résultats dupliqués')
        return self


@router.post('/matching-runs/{run_id}/compare')
def compare(run_id: str, body: CompareIn,
            actor: Principal=Depends(require_role('org_admin','recruiter')),
            db: Session=Depends(get_db)):
    run=run_or_404(db,actor,run_id)
    items=db.scalars(select(MatchingResult).where(
        MatchingResult.run_id==run.id, MatchingResult.id.in_(body.result_ids))).all()
    if len(items)!=len(body.result_ids):
        raise HTTPException(404, 'Résultat étranger ou absent de cette analyse')
    criterion_rows=db.scalars(select(MatchingCriterionResult).where(
        MatchingCriterionResult.result_id.in_([r.id for r in items]))).all()
    matrix={r.id:[] for r in items}
    for criterion in criterion_rows:
        matrix[criterion.result_id].append({'code':criterion.code,'label':criterion.label,
                'state':criterion.state,'contribution':float(criterion.contribution)})
    ordered=sorted(items,key=lambda x:body.result_ids.index(x.id))
    ranked,ranking=ranked_results(db,run)
    rank_by_id={result.id:rank for result,rank in ranked}
    return {'items':[{**result_info(r),**rank_by_id.get(r.id,{}),'stale':is_result_stale(db,run,r),'criteria':sorted(matrix[r.id],key=lambda x:x['code'])}
                     for r in ordered],
            'ranking':ranking,
            'note':'Aucun gagnant automatique. Examiner les preuves individuellement.'}


@router.post('/matching-results/{result_id}/request-review', status_code=201)
def request_review(result_id: str,
          actor: Principal=Depends(require_role('org_admin','recruiter')),
          db: Session=Depends(get_db)):
    result,run=result_or_404(db,actor,result_id)
    application=db.scalar(select(Application).where(Application.id==result.application_id,
                  Application.organization_id==actor.organization.id))
    if application is None:
        raise HTTPException(404,'Candidature introuvable')
    review=ApplicationReview(application_id=application.id,author_id=actor.user.id,
            finding='needs_clarification',note='Vérification humaine des critères documentaires demandée.')
    application.review_status='needs_clarification'
    db.add(review)
    db.flush()
    record(db,actor,'matching.review.requested','application',application.id,
           {'result_id':result_id,'review_id':review.id})
    db.commit()
    return {'review_id':review.id,'application_id':application.id,'review_status':application.review_status}
