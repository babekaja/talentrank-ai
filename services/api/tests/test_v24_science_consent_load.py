"""V24 verification: no fake neural scores, explicit consent, fairness privacy, real-load harness."""
import io
import json
import zipfile
from copy import deepcopy
from app.ml.neural_eval_v24 import benchmark, validate_corpus
from app.ml.fairness_lab_v24 import paired_audit, group_audit
from app.api.v1 import candidate_portal
from test_recruitment import auth_headers
from app.models import CandidatePortalToken, CandidateConsentEvent
from app.main import app
from app.core.database import get_db
from scripts.benchmark_3000_v24 import archive_chunk
import pytest


def toy_corpus():
    passages=[]; queries=[]
    for split,n in [('train',0),('validation',1),('test',2)]:
        passages.extend([
            {'id':f'{n}a','text':f'Développement Angular de l’application {n}',
             'organization_id':'o1','document_id':f'{n}docA','split':split},
            {'id':f'{n}b','text':f'Sans expérience Angular {n}',
             'organization_id':'o1','document_id':f'{n}docB','split':split},
            {'id':f'{n}c','text':f'Angular is useful for web {n}',
             'organization_id':'o2','document_id':f'{n}docOther','split':split},
        ])
        queries.append({'id':f'{n}q','requirement':'Expérience Angular démontrée',
             'split':split,'language':'fr' if n<2 else 'en',
             'family_id':f'family{n}', 'organization_id':'o1',
             'authorized_documents':[f'{n}docA',f'{n}docB'],
             'relevant_passage_ids':[f'{n}a'],
             'annotator_ids':['R1','R2']})
    return {'passages':passages,'queries':queries}


def test_neural_baselines_never_claim_real_training():
    d=toy_corpus()
    result=benchmark(d)
    assert result['neural_inference_executed'] is False
    assert result['deployment_enabled'] is False
    assert result['scientific_readiness']=='insufficient_evidence'
    assert set(result['methods_executed'])=={'bm25','tfidf'}
    assert result['test_languages']['en']==1
    assert 'o2' not in json.dumps(result)
    assert all('passages' not in k for k in result)


def test_neural_fake_encoder_only_proves_adapter_not_model():
    class Encoder:
        def encode(self,texts):
            return [[1.,0.] if 'Angular' in t else [0.,1.] for t in texts]
    result=benchmark(toy_corpus(),encoder=Encoder())
    assert result['neural_inference_executed']
    assert result['deployment_enabled'] is False
    assert 'neural' in result['methods_executed']


@pytest.mark.parametrize('mutation', ['same_document','same_family','duplicate_text','wrong_scope','one_annotator'])
def test_neural_corpus_rejects_data_leakage(mutation):
    d=toy_corpus()
    if mutation=='same_document':d['passages'][0]['document_id']=d['passages'][-2]['document_id']
    if mutation=='same_family':d['queries'][-1]['family_id']=d['queries'][0]['family_id']
    if mutation=='duplicate_text':d['passages'][-1]['text']=d['passages'][0]['text']
    if mutation=='wrong_scope':d['queries'][-1]['relevant_passage_ids']=['0a']
    if mutation=='one_annotator':d['queries'][-1]['annotator_ids']=['R1']
    with pytest.raises(ValueError):validate_corpus(d)


def test_counterfactual_audit_on_real_extractor():
    aliases=[('skill-angular','angular','angular')]
    rows=[{'pair_id':'a','variation_type':'identity',
           'original_text':'J’ai réalisé un portail pour un client.',
           'variant_text':'Nom : Angular Martin. J’ai réalisé un portail pour un client.'},
          {'pair_id':'b','variation_type':'address_proxy',
           'original_text':'J’ai développé une application Angular.',
           'variant_text':'Adresse : Bukavu. J’ai développé une application Angular.'}]
    r=paired_audit(rows,aliases)
    assert r['pairs']==2 and r['changed_pairs']>=1
    assert 'Angular Martin' not in json.dumps(r)
    assert r['status'].endswith('not_fairness_certification')


def test_group_audit_suppresses_small_groups_and_no_divide_by_zero():
    rows=[{'group_code':'X','true_support':bool(i%2),'predicted_support':bool(i%2)} for i in range(12)]
    rows +=[{'group_code':'Y','true_support':False,'predicted_support':False} for _ in range(4)]
    result=group_audit(rows,min_group_size=10)
    assert result['groups_suppressed']==1 and 'Y' not in result['metrics_by_group']
    assert result['gaps']['false_positive_rate'] is None
    with pytest.raises(ValueError):group_audit([{'group_code':'A','true_support':1,'predicted_support':True}]*10)


def test_load_generator_produces_actual_valid_documents():
    content=archive_chunk(0,5)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        assert len(z.infolist())==5
        assert z.testzip() is None
        names=z.namelist()
        assert len(set(names))==5
        for item in z.infolist():
            assert item.filename.endswith('.docx') and item.file_size>1000


def test_portal_requires_reliable_email_service(client_and_orgs):
    client,_=client_and_orgs;h=auth_headers(client)
    candidate=client.post('/api/v1/candidates',json={'full_name':'Test consent','email':'test-con@example.org'},headers=h).json()
    result=client.post(f'/api/v1/candidate-portal/candidates/{candidate["id"]}/send-access-code',headers=h)
    assert result.status_code==503
    assert client.get('/api/v1/candidate-portal/me').status_code==503


def test_candidate_verified_consent_and_withdrawal(client_and_orgs,monkeypatch):
    client,_=client_and_orgs;h=auth_headers(client)
    candidate=client.post('/api/v1/candidates',json={'full_name':'Candidate owner','email':'owner@example.org'},headers=h).json()
    codes=[]
    monkeypatch.setattr(candidate_portal,'require_portal_enabled',lambda:None)
    monkeypatch.setattr(candidate_portal,'deliver_candidate_code',lambda addr,code:codes.append((addr,code)))
    url=f'/api/v1/candidate-portal/candidates/{candidate["id"]}/send-access-code'
    assert client.post(url).status_code==401
    sent=client.post(url,headers=h)
    assert sent.status_code==202 and 'code' not in sent.json()
    assert codes[0][0]=='owner@example.org'
    assert client.post(url,headers=h).status_code==429
    wrong=client.post('/api/v1/candidate-portal/verify',json={'code':'n'*42})
    assert wrong.status_code==401
    verified=client.post('/api/v1/candidate-portal/verify',json={'code':codes[0][1]})
    assert verified.status_code==200
    assert client.post('/api/v1/candidate-portal/verify',json={'code':codes[0][1]}).status_code==401
    p_headers={'Authorization':'Bearer '+verified.json()['access_token']}
    assert client.get('/api/v1/candidate-portal/me',headers=p_headers).json()['training_consent'] is False
    assert client.get('/api/v1/candidate-portal/training-suggestions',headers=p_headers).json()['status']=='consent_required'
    assert client.put('/api/v1/candidate-portal/consent',headers=p_headers,json={'consent':True,'notice_version':'bad'}).status_code==422
    r=client.put('/api/v1/candidate-portal/consent',headers=p_headers,json={'consent':True,'notice_version':candidate_portal.NOTICE_VERSION})
    assert r.status_code==200
    assert client.get('/api/v1/candidate-portal/me',headers=p_headers).json()['training_consent'] is True
    assert client.put('/api/v1/candidate-portal/consent',headers=p_headers,json={'consent':False,'notice_version':candidate_portal.NOTICE_VERSION}).status_code==200
    assert client.get('/api/v1/candidate-portal/training-suggestions',headers=p_headers).json()['status']=='consent_required'
    with next(app.dependency_overrides[get_db]()) as db:
        events=db.query(CandidateConsentEvent).filter(CandidateConsentEvent.candidate_id==candidate['id']).all()
        assert [event.action for event in events]==['granted','withdrawn']
        assert all(event.source=='candidate_portal' for event in events)
    assert client.post('/api/v1/candidate-portal/logout',headers=p_headers).status_code==200
    assert client.get('/api/v1/candidate-portal/me',headers=p_headers).status_code==401


def test_candidate_access_code_cannot_cross_organization(client_and_orgs,monkeypatch):
    from app.models import OrganizationMember, User
    from app.core.security import hash_password
    client,ids=client_and_orgs
    headers=auth_headers(client)
    row=client.post('/api/v1/candidates',json={'full_name':'Secret candidate',
          'email':'secret-candidate@example.org'},headers=headers)
    assert row.status_code==201
    cid=row.json()['id']
    with next(app.dependency_overrides[get_db]()) as db:
        other=User(email='portal-admin@beta.example.org',full_name='Beta admin',
                   password_hash=hash_password('secure-beta-pass-123'))
        db.add(other);db.flush()
        db.add(OrganizationMember(user_id=other.id,organization_id=ids['beta'],role='org_admin'))
        db.commit()
    beta=client.post('/api/v1/auth/login',json={'email':'portal-admin@beta.example.org',
                     'password':'secure-beta-pass-123','organization_slug':'beta'})
    assert beta.status_code==200
    beta_headers={'Authorization':'Bearer '+beta.json()['access_token']}
    monkeypatch.setattr(candidate_portal,'require_portal_enabled',lambda:None)
    monkeypatch.setattr(candidate_portal,'deliver_candidate_code',lambda *_:None)
    result=client.post(f'/api/v1/candidate-portal/candidates/{cid}/send-access-code',headers=beta_headers)
    assert result.status_code==422
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.query(CandidatePortalToken).count()==0


def test_pipeline_progress_scoped_to_organization(client_and_orgs):
    client,_=client_and_orgs
    headers=auth_headers(client)
    response=client.get('/api/v1/uploads/batches/not-found/pipeline-progress',headers=headers)
    assert response.status_code==404
    assert client.get('/api/v1/uploads/batches/not-found/pipeline-progress').status_code==401


def test_administrative_preference_is_not_self_service_consent(client_and_orgs):
    from app.models import OpportunityPreference
    from app.models.auth import User
    client,ids=client_and_orgs
    h=auth_headers(client)
    candidate=client.post('/api/v1/candidates',json={'full_name':'Consent separated'},headers=h).json()
    old=client.put(f'/api/v1/africa/opportunities/candidates/{candidate["id"]}/preference',headers=h,
                   json={'state':'opt_in_recorded','evidence_reference':'Legacy administrative indication only'})
    assert old.status_code==200
    with next(app.dependency_overrides[get_db]()) as db:
        assert candidate_portal.current_consent(db,candidate['id'],ids['alpha']) is False
