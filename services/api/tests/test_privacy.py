"""Phase 7: authorization, legal hold, storage failure, source and derived-data deletion."""
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.main import app
from app.core.database import get_db
from app.documents.storage import get_storage
from app.models.auth import utcnow
from app.models import (Candidate, CVDocument, CandidateContact, Application, ApplicationReview,
    OrganizationMember, User, UploadBatch, ProcessingTask, DocumentPage, ExtractionWarning,
    DocumentNlpRun, RetentionPolicy, MatchingRun, MatchingResult, MatchingCriterionResult,
    MatchingEvidence, AuditLog)
from app.core.security import hash_password
from test_recruitment import auth_headers, new_job, requirements

class Storage:
    def __init__(self): self.deleted=[];self.fail=False
    def delete(self,key):
        if self.fail: raise OSError('unavailable')
        self.deleted.append(key)


def setup_candidate(client, headers, org_id, *, active=False):
    job=new_job(client,headers).json()['id']
    assert client.put(f'/api/v1/jobs/{job}/requirements',headers=headers,json=requirements()).status_code==200
    assert client.post(f'/api/v1/jobs/{job}/requirements/confirm',headers=headers,
                       json={'expected_version':1}).status_code==200
    campaign=client.post('/api/v1/campaigns',headers=headers,
                         json={'name':'Phase 7','job_id':job}).json()['id']
    client.patch(f'/api/v1/campaigns/{campaign}/status',headers=headers,json={'status':'active'})
    candidate=client.post('/api/v1/candidates',headers=headers,
                          json={'full_name':'Personne de test','email':'test-person@example.org'}).json()['id']
    application=client.post('/api/v1/applications',headers=headers,
         json={'candidate_id':candidate,'campaign_id':campaign}).json()['id']
    if not active:
        client.patch(f'/api/v1/campaigns/{campaign}/status',headers=headers,json={'status':'closed'})
    return campaign,candidate,application


def seed_document_and_run(org_id, campaign_id, candidate_id, app_id):
    db=next(app.dependency_overrides[get_db]())
    try:
        org_user=db.scalar(select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id==org_id))
        batch=UploadBatch(organization_id=org_id,campaign_id=campaign_id,created_by=org_user)
        db.add(batch);db.flush()
        doc=CVDocument(organization_id=org_id,batch_id=batch.id,campaign_id=campaign_id,
           application_id=app_id,filename='document.pdf',sha256='f'*64,
           content_type='application/pdf',byte_size=600,object_key=f'{org_id}/private/object',
           status='completed')
        db.add(doc);db.flush()
        db.add(ProcessingTask(document_id=doc.id,status='completed'))
        page=DocumentPage(document_id=doc.id,page_number=1,text='JavaScript et Angular',
            extraction_method='pdfplumber',version='1')
        db.add(page);db.flush()
        db.add(ExtractionWarning(document_id=doc.id,code='TEST',message='Essai'))
        db.add(DocumentNlpRun(organization_id=org_id,document_id=doc.id,
             status='completed',rules_version='1',taxonomy_fingerprint='0'*64,
             content_fingerprint='a'*64))
        run=MatchingRun(organization_id=org_id,campaign_id=campaign_id,job_id=None,
            criteria_version=1,config_version=1,algorithm_version='test',
            weights_snapshot={},requirements_snapshot=[],application_ids_snapshot=[app_id],
            skill_mapping_snapshot={},status='completed',total=1,processed=1,
            created_by=org_user)
        from app.models import RecruitmentCampaign
        run.job_id=db.get(RecruitmentCampaign,campaign_id).job_id
        db.add(run);db.flush()
        result=MatchingResult(run_id=run.id,application_id=app_id,candidate_id=candidate_id,
           score=20,state='partial_review_required',documented=1,to_review=0,
           not_documented=1,evidence_fingerprint='a'*64,group_coverage={})
        db.add(result);db.flush()
        criterion=MatchingCriterionResult(result_id=result.id,requirement_id='q'*36,
           code='TEST',label='Angular',group_code='essential',state='documented_mention',
           weight=1,contribution=20,note_code='EXACT_SOURCE_MENTION')
        db.add(criterion);db.flush()
        db.add(MatchingEvidence(criterion_result_id=criterion.id,document_id=doc.id,
            page_id=page.id,page_number=1,start_offset=0,end_offset=7,
            matched_text='Angular',verification_status='mentioned'))
        db.commit()
        return doc.id, doc.object_key, run.id
    finally:db.close()


def test_retention_policy_hold_and_due(client_and_orgs):
    client,ids=client_and_orgs;h=auth_headers(client)
    app.dependency_overrides[get_storage]=lambda: Storage()
    cid=client.post('/api/v1/candidates',headers=h,json={'full_name':'Ancien'}).json()['id']
    assert client.get('/api/v1/privacy/retention',headers=h).json()['retention_days']==365
    assert client.put('/api/v1/privacy/retention',headers=h,json={'retention_days':5}).status_code==422
    assert client.put('/api/v1/privacy/retention',headers=h,json={'retention_days':30}).status_code==200
    with next(app.dependency_overrides[get_db]()) as db:
        row=db.get(Candidate,cid);row.created_at=utcnow()-timedelta(days=50);db.commit()
    assert cid in [x['id'] for x in client.get('/api/v1/privacy/candidates/due',headers=h).json()['items']]
    assert client.put(f'/api/v1/privacy/candidates/{cid}/hold',headers=h,
           json={'active':True,'reason':'Conservation demandée dans le dossier.'}).status_code==200
    assert client.get(f'/api/v1/privacy/candidates/{cid}/erasure-preview',headers=h).json()['legal_hold']
    assert cid not in [x['id'] for x in client.get('/api/v1/privacy/candidates/due',headers=h).json()['items']]
    assert client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
           json={'confirmation':'SUPPRIMER'}).status_code==409
    assert client.put(f'/api/v1/privacy/candidates/{cid}/hold',headers=h,
           json={'active':False,'reason':'Fin de conservation légale autorisée.'}).status_code==200


def test_privacy_external_error_and_complete_erasure(client_and_orgs):
    client,ids=client_and_orgs;h=auth_headers(client)
    camp,cid,app_id=setup_candidate(client,h,ids['alpha'])
    doc,key,run=seed_document_and_run(ids['alpha'],camp,cid,app_id)
    # Enable FK enforcement to catch unsafe deletion order even on SQLite.
    from sqlalchemy import text
    with next(app.dependency_overrides[get_db]()) as db:
        db.execute(text('PRAGMA foreign_keys = ON')); db.commit()
    store=Storage()
    app.dependency_overrides[get_storage]=lambda: store
    try:
        preview=client.get(f'/api/v1/privacy/candidates/{cid}/erasure-preview',headers=h)
        assert preview.status_code==200 and preview.json()['documents']==1
        assert preview.json()['analyses_impactees']==1
        assert client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                           json={'confirmation':'OUI'}).status_code==422
        store.fail=True
        fail=client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                          json={'confirmation':'SUPPRIMER'})
        assert fail.status_code==503,fail.text
        assert client.get(f'/api/v1/candidates/{cid}',headers=h).status_code==200
        store.fail=False
        success=client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                            json={'confirmation':'SUPPRIMER'})
        assert success.status_code==200,success.text
        assert success.json()['documents']==1 and key in store.deleted
        assert client.get(f'/api/v1/candidates/{cid}',headers=h).status_code==404
        assert client.get(f'/api/v1/documents/{doc}',headers=h).status_code==404
        assert client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                           json={'confirmation':'SUPPRIMER'}).status_code==404
        with next(app.dependency_overrides[get_db]()) as db:
            assert db.get(MatchingRun,run) is None
            assert db.get(Application,app_id) is None
            assert db.scalar(select(AuditLog).where(AuditLog.resource_id==cid)) is None
            assert db.scalar(select(AuditLog).where(AuditLog.action=='privacy.candidate.erased'))
    finally:app.dependency_overrides.pop(get_storage,None)


def test_erasure_prevented_for_active_campaign(client_and_orgs):
    client,ids=client_and_orgs;h=auth_headers(client)
    camp,cid,app_id=setup_candidate(client,h,ids['alpha'],active=True)
    store=Storage();app.dependency_overrides[get_storage]=lambda:store
    try:
        result=client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                           json={'confirmation':'SUPPRIMER'})
        assert result.status_code==409
        assert client.get(f'/api/v1/candidates/{cid}',headers=h).status_code==200
    finally:app.dependency_overrides.pop(get_storage,None)


def test_erasure_cross_tenant_disallowed(client_and_orgs):
    client,ids=client_and_orgs;h=auth_headers(client)
    app.dependency_overrides[get_storage]=lambda: Storage()
    candidate=client.post('/api/v1/candidates',headers=h,json={'full_name':'Alpha secret'}).json()['id']
    with next(app.dependency_overrides[get_db]()) as db:
        user=User(email='privacy-beta@example.org',full_name='Beta admin',
                  password_hash=hash_password('secure-pass-6789'))
        db.add(user);db.flush();db.add(OrganizationMember(organization_id=ids['beta'],
          user_id=user.id,role='org_admin'));db.commit()
    login=client.post('/api/v1/auth/login',json={'organization_slug':'beta',
      'email':'privacy-beta@example.org','password':'secure-pass-6789'})
    bh={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.get(f'/api/v1/privacy/candidates/{candidate}/erasure-preview',headers=bh).status_code==404
    assert client.post(f'/api/v1/privacy/candidates/{candidate}/erase',headers=bh,
                       json={'confirmation':'SUPPRIMER'}).status_code==404
    assert client.get('/api/v1/privacy/candidates/due',headers=bh).json()['items']==[]
    assert client.get(f'/api/v1/candidates/{candidate}',headers=h).status_code==200


def test_erasure_blocked_if_nlp_is_processing(client_and_orgs):
    client,ids=client_and_orgs;h=auth_headers(client)
    camp,cid,app_id=setup_candidate(client,h,ids['alpha'])
    doc,key,run=seed_document_and_run(ids['alpha'],camp,cid,app_id)
    with next(app.dependency_overrides[get_db]()) as db:
        nlp=db.scalar(select(DocumentNlpRun).where(DocumentNlpRun.document_id==doc))
        nlp.status='processing';db.commit()
    store=Storage();app.dependency_overrides[get_storage]=lambda:store
    try:
        r=client.post(f'/api/v1/privacy/candidates/{cid}/erase',headers=h,
                      json={'confirmation':'SUPPRIMER'})
        assert r.status_code==409
        assert store.deleted==[]
    finally:app.dependency_overrides.pop(get_storage,None)
