"""Phase 6: source-grounded analytics, quality controls, gaps and audited exports."""
from collections import Counter
from hashlib import sha256
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Job, RecruitmentCampaign, Candidate, Application, ApplicationReview,
    UploadBatch, CVDocument, DocumentPage, ExtractionWarning, SkillEvidence, Skill,
    MatchingRun, MatchingResult, MatchingCriterionResult, MatchingEvidence, ReportExport)
from app.api.v1.documents import scoped_document
from app.api.v1.matching import result_or_404, run_or_404
from app.insights.quality import inspect_pages
from app.insights.exports import csv_bytes, xlsx_bytes, pdf_bytes
from app.insights.exports import RANKED_COLUMNS
from app.ml.documentary_ranking import ranked_results
from app.services.audit import record

router=APIRouter()


def count(db, model, condition):
    return int(db.scalar(select(func.count()).select_from(model).where(condition)) or 0)


@router.get('/dashboard/overview')
def overview(actor: Principal = Depends(require_role('org_admin','recruiter')),
             db: Session = Depends(get_db)):
    org=actor.organization.id
    j=Job.organization_id==org
    c=RecruitmentCampaign.organization_id==org
    a=Application.organization_id==org
    d=CVDocument.organization_id==org
    r=MatchingRun.organization_id==org
    cards={
        'jobs':count(db,Job,j),
        'jobs_active':count(db,Job,j & (Job.status=='open')),
        'campaigns':count(db,RecruitmentCampaign,c),
        'campaigns_active':count(db,RecruitmentCampaign,c & (RecruitmentCampaign.status=='active')),
        'applications':count(db,Application,a),
        'applications_to_review':count(db,Application,a & (Application.review_status=='to_review')),
        'documents':count(db,CVDocument,d),
        'documents_completed':count(db,CVDocument,d & (CVDocument.status.in_(['completed','needs_review']))),
        'documents_failed':count(db,CVDocument,d & (CVDocument.status=='failed')),
        'analyses':count(db,MatchingRun,r),
        'analyses_completed':count(db,MatchingRun,r & (MatchingRun.status=='completed')),
    }
    cards['applications_human_reviewed']=int(db.scalar(select(func.count(func.distinct(ApplicationReview.application_id)))
        .join(Application,Application.id==ApplicationReview.application_id)
        .where(Application.organization_id==org)) or 0)
    doc_states=db.execute(select(CVDocument.status,func.count(CVDocument.id)).where(d)
        .group_by(CVDocument.status).order_by(CVDocument.status)).all()
    campaign_rows=db.execute(select(RecruitmentCampaign.id,RecruitmentCampaign.name,func.count(Application.id))
        .outerjoin(Application,(Application.campaign_id==RecruitmentCampaign.id)&
                    (Application.organization_id==org))
        .where(c).group_by(RecruitmentCampaign.id,RecruitmentCampaign.name)
        .order_by(func.count(Application.id).desc(),RecruitmentCampaign.id).limit(12)).all()
    daily=db.execute(select(func.date(Application.created_at),func.count(Application.id)).where(a)
        .group_by(func.date(Application.created_at)).order_by(func.date(Application.created_at).desc()).limit(30)).all()
    # Skills reflect CONFIRMED job requirements, not inferred candidate characteristics.
    from app.models import JobRequirement
    top_skills=db.execute(select(JobRequirement.label,func.count(JobRequirement.id))
        .join(Job,Job.id==JobRequirement.job_id)
        .where(Job.organization_id==org,Job.criteria_confirmed_at.is_not(None),
               JobRequirement.category=='skill')
        .group_by(JobRequirement.label).order_by(func.count(JobRequirement.id).desc(),JobRequirement.label)
        .limit(10)).all()
    return {'cards':cards,
            'document_states':[{'status':status,'count':qty} for status,qty in doc_states],
            'campaigns':[{'id':cid,'name':name,'applications':qty} for cid,name,qty in campaign_rows],
            'applications_daily':[{'day':str(day),'count':qty} for day,qty in reversed(daily)],
            'skills_demanded':[{'label':label,'count':qty} for label,qty in top_skills],
            'note':'Comptages réels limités à votre organisation. Aucun jeu de démonstration injecté.'}


@router.get('/documents/{document_id}/viewer')
def viewer(document_id:str,page_number:int|None=Query(None,ge=1),
          actor: Principal=Depends(require_role('org_admin','recruiter')),
          db:Session=Depends(get_db)):
    doc=scoped_document(document_id,actor,db)
    stmt=select(DocumentPage).where(DocumentPage.document_id==doc.id)
    if page_number is not None: stmt=stmt.where(DocumentPage.page_number==page_number)
    pages=db.scalars(stmt.order_by(DocumentPage.page_number).limit(150)).all()
    mentions=db.execute(select(SkillEvidence,Skill).join(Skill,Skill.id==SkillEvidence.skill_id)
        .where(SkillEvidence.organization_id==actor.organization.id,
               SkillEvidence.document_id==doc.id,SkillEvidence.page_id.in_([p.id for p in pages]))) .all() if pages else []
    by_page={p.id:[] for p in pages}
    for mention,skill in mentions:
        p=next((x for x in pages if x.id==mention.page_id),None)
        if p and 0<=mention.start_offset<mention.end_offset<=len(p.text) and \
           p.text[mention.start_offset:mention.end_offset]==mention.matched_text:
            by_page[p.id].append({'start':mention.start_offset,'end':mention.end_offset,
                 'text':mention.matched_text,'label':skill.label_fr,'status':mention.status})
    record(db,actor,'document.viewer.viewed','document',doc.id)
    db.commit()
    return {'document_id':doc.id,'filename':doc.filename,'total_pages':doc.page_count,
        'pages':[{'number':p.page_number,'text':p.text,'method':p.extraction_method,
                  'mentions':sorted(by_page[p.id],key=lambda x:x['start'])} for p in pages],
        'note':'Surlignage dans le texte extrait. Positions dans le PDF original non garanties.'}


@router.get('/documents/{document_id}/quality')
def document_quality(document_id:str,
          actor:Principal=Depends(require_role('org_admin','recruiter')),
          db:Session=Depends(get_db)):
    doc=scoped_document(document_id,actor,db)
    pages=db.scalars(select(DocumentPage).where(DocumentPage.document_id==doc.id)
         .order_by(DocumentPage.page_number).limit(150)).all()
    stored=db.scalars(select(ExtractionWarning).where(ExtractionWarning.document_id==doc.id)
            .order_by(ExtractionWarning.page_number).limit(100)).all()
    flags=[{'page_number':x.page_number,'code':x.code,'severity':'review',
            'message':x.message,'source_excerpt':None} for x in stored]
    flags+=inspect_pages(pages)
    return {'document_id':doc.id,'processing_status':doc.status,
            'quality_state':'review_required' if flags or doc.status!='completed' else 'no_alert_detected',
            'flags':flags[:150],
            'limitations':['Analyse du texte extrait, pas une preuve de fraude.',
              'Chevauchements de carrière et équivalences de diplômes non évalués automatiquement.',
              'Une absence d’alerte ne garantit pas l’exactitude du CV.']}


@router.get('/matching-results/{result_id}/gaps')
def gaps(result_id:str,
         actor:Principal=Depends(require_role('org_admin','recruiter')),
         db:Session=Depends(get_db)):
    result,run=result_or_404(db,actor,result_id)
    rows=db.scalars(select(MatchingCriterionResult)
        .where(MatchingCriterionResult.result_id==result.id)
        .order_by(MatchingCriterionResult.group_code,MatchingCriterionResult.code)).all()
    evidence_count=dict(db.execute(select(MatchingEvidence.criterion_result_id,
        func.count(MatchingEvidence.id)).where(
        MatchingEvidence.criterion_result_id.in_([x.id for x in rows]))
        .group_by(MatchingEvidence.criterion_result_id)).all()) if rows else {}
    entries=[{'code':x.code,'label':x.label,'category':x.group_code,
        'state':x.state,'contribution':float(x.contribution),
        'has_source':evidence_count.get(x.id,0)>0,'note_code':x.note_code} for x in rows]
    summary=(result.group_coverage or {}).get('summary',{})
    return {'result_id':result.id,'run_id':run.id,'score':float(result.score) if result.score is not None and result.state=='documentary_coverage' else None,
        'evaluable_subset_coverage':summary.get('evaluable_subset_coverage'),
        'assessable_weight_percent':summary.get('assessable_weight_percent'),
        'documented':[x for x in entries if x['state']=='documented_mention'],
        'needs_review':[x for x in entries if x['state'] in ('needs_review','manual_review_required')],
        'not_found':[x for x in entries if x['state'] in ('not_documented','not_found')],
        'other':[x for x in entries if x['state'] not in ('documented_mention','needs_review',
                                               'manual_review_required','not_documented','not_found')],
        'warning':'La couverture affichée porte uniquement sur les critères évaluables automatiquement. Non retrouvé dans le CV ne signifie pas non maîtrisé. Aucune recommandation de formation non vérifiée.'}


def report_dataset(db,actor,campaign_id,run_id):
    campaign=db.scalar(select(RecruitmentCampaign).where(RecruitmentCampaign.id==campaign_id,
                                                RecruitmentCampaign.organization_id==actor.organization.id))
    if campaign is None:raise HTTPException(404,'Campagne introuvable')
    q=select(MatchingRun).where(MatchingRun.organization_id==actor.organization.id,
                MatchingRun.campaign_id==campaign_id,MatchingRun.status=='completed')
    if run_id:q=q.where(MatchingRun.id==run_id)
    run=db.scalar(q.order_by(MatchingRun.completed_at.desc(),MatchingRun.id.desc()).limit(1))
    if run is None:raise HTTPException(409,'Aucune analyse terminée disponible pour cette campagne')
    matches,_=ranked_results(db,run)
    reviews=dict(db.execute(select(Application.id,Application.review_status).where(
        Application.organization_id==actor.organization.id,
        Application.campaign_id==campaign.id)).all())
    rows=[(ranking['rank'] if ranking['rank'] is not None else 'Non classé',
           ranking['candidate_reference'],str(result.application_id),
           ranking['matching_percentage'] if ranking['matching_percentage'] is not None else 'Non calculable',
           ranking['ranking_scope_percent'],
           {'documentary_coverage':'Critères vérifiés','partial_review_required':'À vérifier',
            'awaiting_documents':'Documents attendus'}.get(result.state,result.state.replace('_',' ')),
           result.documented,result.to_review,result.not_documented,
           {'pending':'En attente','to_review':'À examiner','reviewed':'Avis enregistré',
            'needs_clarification':'À préciser','shortlisted':'Présélectionné'}.get(
                reviews.get(result.application_id,''),reviews.get(result.application_id,'').replace('_',' ')))
          for result,ranking in matches]
    return campaign,run,rows


@router.get('/reports/campaigns/{campaign_id}')
def report(campaign_id:str,format:str=Query('csv',pattern='^(csv|xlsx|pdf)$'),run_id:str|None=None,
           actor:Principal=Depends(require_role('org_admin','recruiter')),
           db:Session=Depends(get_db)):
    campaign,run,rows=report_dataset(db,actor,campaign_id,run_id)
    title=f'TalentRank AI - Classement - {campaign.name} - Analyse {run.id[:8]}'
    if format=='xlsx':raw=xlsx_bytes(rows,title,columns=RANKED_COLUMNS);media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='pdf':raw=pdf_bytes(rows,title,columns=RANKED_COLUMNS);media='application/pdf'
    else:raw=csv_bytes(rows,columns=RANKED_COLUMNS);media='text/csv; charset=utf-8'
    entry=ReportExport(organization_id=actor.organization.id,campaign_id=campaign.id,run_id=run.id,
           format=format,row_count=len(rows),sha256=sha256(raw).hexdigest(),created_by=actor.user.id)
    db.add(entry)
    db.flush()
    record(db,actor,'report.exported','report_export',entry.id,
           {'format':format,'campaign_id':campaign.id,'run_id':run.id,'row_count':len(rows)})
    db.commit()
    return Response(content=raw,media_type=media,headers={
       'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
       'Content-Disposition':f'attachment; filename="talentrank-{campaign.id[:8]}-{run.id[:8]}.{format}"'})


@router.get('/reports/history')
def export_history(limit:int=Query(30,ge=1,le=100),
       actor:Principal=Depends(require_role('org_admin','recruiter')),
       db:Session=Depends(get_db)):
    exports=db.scalars(select(ReportExport).where(ReportExport.organization_id==actor.organization.id)
        .order_by(ReportExport.created_at.desc(),ReportExport.id.desc()).limit(limit)).all()
    return {'items':[{'id':x.id,'campaign_id':x.campaign_id,'run_id':x.run_id,
       'format':x.format,'row_count':x.row_count,'sha256':x.sha256,'created_at':x.created_at} for x in exports]}
