"""Phase 5: synthetic-only exact-document matching; no autonomous outcomes."""
from decimal import Decimal
from sqlalchemy import select
from app.main import app
from app.core.database import get_db
from app.ml.matching import calculate, DEFAULT_WEIGHTS
from app.ml.matching_service import execute_matching_run
from app.ml.terminology import seed_glossary
from app.ml.processing import analyze_document
from app.documents.processing import process_document
from app.documents.storage import get_storage
from app.models import (Skill, OrganizationMember, User, MatchingResult, Application,
                        MatchingRun)
from app.core.security import hash_password
from test_documents import FakeStorage, docx_bytes, create_batch, override_storage
from test_recruitment import auth_headers, new_job


def test_pure_scoring_and_non_skill_limits():
    req=[{'id':'a','code':'angular','label':'Angular','category':'skill','required':True,'weight':2},
         {'id':'b','code':'python','label':'Python','category':'skill','required':True,'weight':2},
         {'id':'c','code':'diploma','label':'Diplôme','category':'qualification','required':False,'weight':1}]
    evidence={'ang':[{'id':'e1','document_id':'d','page_number':1,'start_offset':0,'status':'mentioned',
                       'source_valid':True}]}
    mapping={'a':'ang','b':'py','c':None}
    result=calculate(req,DEFAULT_WEIGHTS,evidence,mapping,documents_ready=True,document_fingerprint='fp')
    assert result.score is None  # incomplete assessment cannot be displayed as a global score
    assert result.group_coverage['summary']['evaluable_subset_coverage'] == 50.0
    assert result.state=='partial_review_required'
    assert next(c for c in result.criteria if c.requirement['id']=='c').state=='manual_review_required'
    assert calculate(req,DEFAULT_WEIGHTS,evidence,mapping,
                     documents_ready=False,document_fingerprint='fp').score is None
    assert calculate(req,DEFAULT_WEIGHTS,{},mapping,documents_ready=True,document_fingerprint='fp').score is None
    assert calculate(req,DEFAULT_WEIGHTS,evidence,mapping,documents_ready=True,document_fingerprint='fp').fingerprint==result.fingerprint
    changed={'ang':[{**evidence['ang'][0],'status':'rejected'}]}
    assert calculate(req,DEFAULT_WEIGHTS,changed,mapping,documents_ready=True,document_fingerprint='fp').score is None


def test_matching_api_explanation_review_and_snapshot(client_and_orgs,monkeypatch):
    client,orgs=client_and_orgs
    store=FakeStorage()
    override_storage(store,monkeypatch)
    try:
        h=auth_headers(client)
        db=next(app.dependency_overrides[get_db]())
        try:
            seed_glossary(db)
            code_to_id={s.code:s.id for s in db.scalars(select(Skill)).all()}
        finally:db.close()
        job=new_job(client,h).json()
        requirements={'items':[
             {'code':'angular','label':'Angular','category':'skill','required':True,'weight':3,
              'justification':'Frontend métier','skill_ref':code_to_id['angular']},
             {'code':'python','label':'Python','category':'skill','required':True,'weight':1,
              'justification':'Services backend','skill_ref':code_to_id['python']},
             {'code':'tests','label':'Tests logiciels','category':'skill','required':False,'weight':1,
              'justification':'Qualité projet','skill_ref':code_to_id['automated_testing']},
             {'code':'exp','label':'Expérience technique','category':'experience','required':False,
              'weight':1,'justification':'Expérience professionnelle documentée'},
        ]}
        assert client.put(f'/api/v1/jobs/{job["id"]}/requirements',headers=h,json=requirements).status_code==200
        assert client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm',headers=h,
                           json={'expected_version':1}).status_code==200
        c=client.post('/api/v1/campaigns',headers=h,json={'job_id':job['id'],'name':'Campagne matching'}).json()
        campaign_id=c['id']
        assert client.patch(f'/api/v1/campaigns/{campaign_id}/status',headers=h,json={'status':'active'}).status_code==200
        pending_candidate=client.post('/api/v1/candidates',headers=h,json={'full_name':'Profil Test Beta'}).json()
        assert client.post('/api/v1/applications',headers=h,json={
                'candidate_id':pending_candidate['id'],'campaign_id':campaign_id}).status_code==201
        batch=client.post('/api/v1/uploads/batches',headers=h,json={'campaign_id':campaign_id}).json()['id']
        uploaded=client.post(f'/api/v1/uploads/batches/{batch}/files',headers=h,files={
            'file':('profil.docx',docx_bytes('Projet Angular et TypeScript. Sans expérience en Python.'))})
        assert uploaded.status_code==201,uploaded.text
        doc_id=uploaded.json()['items'][0]['id']
        db=next(app.dependency_overrides[get_db]())
        try:
            assert process_document(doc_id,db,store)=='completed'
            assert analyze_document(doc_id,db)=='completed'
        finally:db.close()
        bad=client.post('/api/v1/matching/configuration',headers=h,json={
            'essential':70,'desirable':20,'experience':20,'projects_training':0})
        assert bad.status_code==422
        config=client.post('/api/v1/matching/configuration',headers=h,json={
            'essential':60,'desirable':20,'experience':10,'projects_training':10})
        assert config.status_code==201,config.text
        from app.api.v1 import matching as matching_api
        monkeypatch.setattr(matching_api,'enqueue_matching',lambda rid:None)
        run_res=client.post(f'/api/v1/jobs/{job["id"]}/matching-runs',headers=h,
                    params={'campaign_id':campaign_id})
        assert run_res.status_code==202,run_res.text
        run_id=run_res.json()['id']
        assert run_res.json()['total']==2
        assert run_res.json()['mapping']=={
            'skill_criteria':3,'mapped':3,'unmapped':0,'mapped_required':2}
        # Applications added later are excluded from the immutable run membership snapshot.
        late=client.post('/api/v1/candidates',headers=h,json={'full_name':'Late Arrival'}).json()
        assert client.post('/api/v1/applications',headers=h,json={
             'candidate_id':late['id'],'campaign_id':campaign_id}).status_code==201
        assert client.post(f'/api/v1/jobs/{job["id"]}/matching-runs',headers=h,
                params={'campaign_id':campaign_id}).status_code==409
        db=next(app.dependency_overrides[get_db]())
        try:
            assert execute_matching_run(run_id,db,page_size=1)=='completed'
            assert execute_matching_run(run_id,db)=='unchanged'
        finally:db.close()
        results=client.get(f'/api/v1/matching-runs/{run_id}/results',headers=h)
        assert results.status_code==200,results.text
        assert results.json()['total']==2
        rows=results.json()['items']
        document_row=next(r for r in rows if r['state']=='partial_review_required')
        missing_row=next(r for r in rows if r['state']=='awaiting_documents')
        assert missing_row['state']=='awaiting_documents'
        assert document_row['score'] is None
        assert document_row['group_coverage']['summary']['evaluable_subset_coverage'] == 69.23
        assert document_row['group_coverage']['summary']['unassessed_weight_percent'] > 0
        explanation=client.get(f'/api/v1/matching-results/{document_row["id"]}/explanation',headers=h)
        assert explanation.status_code==200,explanation.text
        data=explanation.json()
        assert not data['stale']
        angular=next(c for c in data['criteria'] if c['code']=='angular')
        python=next(c for c in data['criteria'] if c['code']=='python')
        assert angular['state']=='documented_mention' and angular['evidence']['matched_text']=='Angular'
        assert angular['evidence']['source_still_matches'] is True
        assert python['state']=='needs_review' and python['contribution']==0
        comparison=client.post(f'/api/v1/matching-runs/{run_id}/compare',headers=h,
               json={'result_ids':[r['id'] for r in rows]})
        assert comparison.status_code==200,comparison.text
        assert [r['id'] for r in comparison.json()['items']]==[r['id'] for r in rows]
        assert all(r['stale'] is False for r in comparison.json()['items'])
        assert all('criteria' in r and 'score' in r for r in comparison.json()['items'])
        assert client.post(f'/api/v1/matching-runs/{run_id}/compare',headers=h,
               json={'result_ids':[rows[0]['id'],rows[0]['id']]}).status_code==422
        # A second organization cannot read matching runs, explanations, comparison or settings.
        db=next(app.dependency_overrides[get_db]())
        try:
            foreign=User(email='beta.matching@example.org',full_name='Tenant Beta',
                         password_hash=hash_password('beta-matching-password-123'))
            db.add(foreign);db.flush()
            db.add(OrganizationMember(user_id=foreign.id,organization_id=orgs['beta'],role='org_admin'))
            db.commit()
        finally:db.close()
        beta=client.post('/api/v1/auth/login',json={'organization_slug':'beta',
           'email':'beta.matching@example.org','password':'beta-matching-password-123'})
        assert beta.status_code==200
        bh={'Authorization':f'Bearer {beta.json()["access_token"]}'}
        assert client.get('/api/v1/matching/configuration',headers=bh).json()['version']==0
        assert client.get(f'/api/v1/matching-runs/{run_id}',headers=bh).status_code==404
        assert client.get(f'/api/v1/matching-runs/{run_id}/results',headers=bh).status_code==404
        assert client.get(f'/api/v1/matching-results/{document_row["id"]}/explanation',headers=bh).status_code==404
        assert client.post(f'/api/v1/matching-runs/{run_id}/compare',headers=bh,
             json={'result_ids':[r['id'] for r in rows]}).status_code==404
        assert client.post(f'/api/v1/matching-results/{document_row["id"]}/request-review',headers=bh).status_code==404
        reviewed=client.post(f'/api/v1/matching-results/{document_row["id"]}/request-review',headers=h)
        assert reviewed.status_code==201,reviewed.text
        db=next(app.dependency_overrides[get_db]())
        try:
            assert db.scalar(select(Application).where(Application.id==document_row['application_id'])).review_status=='needs_clarification'
            # A later human correction marks the previous matching result stale, never quietly auto-updated.
            from app.models import SkillEvidence
            e=db.scalar(select(SkillEvidence).where(SkillEvidence.document_id==doc_id,SkillEvidence.skill_id==code_to_id['angular']))
            e.status='rejected';db.commit()
        finally:db.close()
        explanation=client.get(f'/api/v1/matching-results/{document_row["id"]}/explanation',headers=h).json()
        assert explanation['stale'] is True
        assert explanation['score'] is None  # frozen historical run, no misleading partial score
        assert explanation['criteria_version']==1
    finally:
        app.dependency_overrides.pop(get_storage,None)


def test_cross_tenant_and_invalid_run(client_and_orgs):
    client,orgs=client_and_orgs
    h=auth_headers(client)
    assert client.post('/api/v1/jobs/unknown/matching-runs',headers=h,
                       params={'campaign_id':'unknown'}).status_code==404
    assert client.get('/api/v1/matching-runs/unknown',headers=h).status_code==404
    assert client.get('/api/v1/matching-results/unknown/explanation',headers=h).status_code==404
    assert client.get('/api/v1/matching/configuration',headers=h).json()['version']==0


def test_matching_refuses_a_job_without_catalogue_mapping(client_and_orgs,monkeypatch):
    client,_=client_and_orgs
    h=auth_headers(client)
    job=new_job(client,h).json()
    requirements={'items':[{
        'code':'custom_frontend','label':'Compétence frontend libre','category':'skill',
        'required':True,'weight':3,'justification':'Compétence essentielle au poste',
        'skill_ref':None,
    }]}
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements',headers=h,
                      json=requirements).status_code==200
    assert client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm',headers=h,
                       json={'expected_version':1}).status_code==200
    campaign=client.post('/api/v1/campaigns',headers=h,json={
        'job_id':job['id'],'name':'Campagne sans référentiel'}).json()
    assert client.patch(f'/api/v1/campaigns/{campaign["id"]}/status',headers=h,
                        json={'status':'active'}).status_code==200
    candidate=client.post('/api/v1/candidates',headers=h,json={
        'full_name':'Profil sans référentiel'}).json()
    assert client.post('/api/v1/applications',headers=h,json={
        'candidate_id':candidate['id'],'campaign_id':campaign['id']}).status_code==201
    from app.api.v1 import matching as matching_api
    monkeypatch.setattr(matching_api,'enqueue_matching',lambda rid:None)
    response=client.post(f'/api/v1/jobs/{job["id"]}/matching-runs',headers=h,
                         params={'campaign_id':campaign['id']})
    assert response.status_code==409
    assert 'référentiel' in response.json()['detail']
