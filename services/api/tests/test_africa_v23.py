"""V23 tests: curated graph, synthetic ProofLab, privacy, opportunity consent."""
from app.models import Skill
from app.core.database import get_db
from app.main import app
from app.ml.africa_evaluation import run_benchmark, metrics
from app.ml.fairrank import identity_invariance
from test_recruitment import auth_headers


def test_prooflab_synthetic_reproducibility():
    a,b=run_benchmark(),run_benchmark()
    assert a==b
    assert a['queries']==17
    assert a['validation_status']=='synthetic_only_not_validated_for_recruitment'
    assert set(a['by_language'])=={'en','fr'}
    for item in a['overall'].values():
        assert all(0<=score<=1 for score in item.values())


def test_prooflab_needs_annotations():
    import pytest
    with pytest.raises(ValueError): metrics(['a'],set())


def test_fairness_only_identity_invariance_not_proof():
    check=identity_invariance('J’ai travaillé sur Angular et TypeScript', ['A','B'], [('s','angular','angular')])
    assert check['invariant']
    assert check['variant_count']==2
    assert 'synthetic' in check['status']


def test_graph_access_crud_and_evaluation(client_and_orgs):
    client,ids=client_and_orgs
    h=auth_headers(client)
    with next(app.dependency_overrides[get_db]()) as db:
        s1=Skill(code='TEST_GRAPH_ANG',label_fr='Angular',label_en='Angular',active=True)
        s2=Skill(code='TEST_GRAPH_JS',label_fr='JavaScript',label_en='JavaScript',active=True)
        db.add_all([s1,s2]);db.commit();a,b=s1.id,s2.id
    path='/api/v1/africa/talentgraph/relations'
    assert client.get(path).status_code==401
    assert client.get('/api/v1/africa/prooflab/benchmark',headers=h).json()['queries']==17
    body={'source_skill_id':a,'target_skill_id':b,'relation_type':'related',
          'source_reference':'https://example.org/competences/reference',
          'justification':'Technologies voisines mais non interchangeables.',
          'country_code':'CD'}
    assert client.post(path,headers=h,json={**body,'target_skill_id':a}).status_code==422
    assert client.post(path,headers=h,json={**body,'source_reference':'http://example.org/source'}).status_code==422
    created=client.post(path,headers=h,json=body)
    assert created.status_code==201,created.text
    assert created.json()['effect_on_matching']=='none_without_independent_documentary_evidence'
    assert client.post(path,headers=h,json=body).status_code==409
    assert len(client.get(path,headers=h).json()['items'])==1
    assert client.get(path,headers=h,params={'skill_id':b}).json()['items'][0]['target_skill_id']==b
    assert client.delete(path+'/'+created.json()['id'],headers=h).status_code==200
    assert client.get(path,headers=h).json()['items']==[]


def test_fairrank_api_no_unauthenticated_request(client_and_orgs):
    client,_=client_and_orgs
    path='/api/v1/africa/fairrank/identity-check'
    body={'professional_text':'Développement Angular et TypeScript pour un portail.',
          'synthetic_identity_labels':['Profil A','Profil B']}
    assert client.post(path,json=body).status_code==401
    h=auth_headers(client)
    r=client.post(path,headers=h,json=body)
    assert r.status_code==200,r.text
    assert r.json()['invariant'] is True
    assert not any(k in r.json() for k in ('synthetic_identity_labels','professional_text'))
    assert client.get('/api/v1/africa/multilingual/status',headers=h).json()['languages'][-1]['status'].startswith('experimental')


def test_opportunity_explicit_preference_required(client_and_orgs):
    client,_=client_and_orgs
    h=auth_headers(client)
    candidate=client.post('/api/v1/candidates',headers=h,json={'full_name':'Personne de test'}).json()
    preference=f'/api/v1/africa/opportunities/candidates/{candidate["id"]}/preference'
    assert client.put(preference,json={'state':'opt_in_recorded','evidence_reference':'Accord fictif'},headers={}).status_code==401
    assert client.put(preference,json={'state':'unknown','evidence_reference':'Accord fictif'},headers=h).status_code==422
    changed=client.put(preference,json={'state':'opt_in_recorded','evidence_reference':'Reference autorisation test 01'},headers=h)
    assert changed.status_code==200,changed.text
    assert 'indépendante' in changed.json()['warning']
    assert client.put(preference,json={'state':'withdrawn','evidence_reference':'Demande explicite de retrait'},headers=h).status_code==200


def test_skillsproof_nonexistent_document_is_not_leaked(client_and_orgs):
    client,_=client_and_orgs;h=auth_headers(client)
    r=client.get('/api/v1/africa/skillsproof/documents/not-existing',headers=h)
    assert r.status_code==404


def test_graph_cannot_cross_tenant(client_and_orgs):
    from app.models import OrganizationMember, User
    from app.core.security import hash_password
    client,ids=client_and_orgs
    alpha_h=auth_headers(client)
    with next(app.dependency_overrides[get_db]()) as db:
        source=Skill(code='TEST_AFRICA_SOURCE',label_fr='Source',label_en='Source',active=True)
        target=Skill(code='TEST_AFRICA_TARGET',label_fr='Cible',label_en='Target',active=True)
        beta_user=User(email='africa-admin@beta.example.org',full_name='Admin Beta',
                       password_hash=hash_password('another-secure-password-123'))
        db.add_all([source,target,beta_user]);db.flush()
        db.add(OrganizationMember(organization_id=ids['beta'],user_id=beta_user.id,role='org_admin'))
        db.commit();source_id=source.id;target_id=target.id
    base='/api/v1/africa/talentgraph/relations'
    payload={'source_skill_id':source_id,'target_skill_id':target_id,
             'relation_type':'related','country_code':'CD',
             'source_reference':'https://example.org/source',
             'justification':'Relation professionnelle à vérifier systématiquement.'}
    r=client.post(base,json=payload,headers=alpha_h)
    assert r.status_code==201,r.text
    other=client.post('/api/v1/auth/login',json={'organization_slug':'beta','email':'africa-admin@beta.example.org',
                                  'password':'another-secure-password-123'})
    assert other.status_code==200
    beta_h={'Authorization':'Bearer '+other.json()['access_token']}
    assert client.get(base,headers=beta_h).json()['items']==[]
    assert client.delete(base+'/'+r.json()['id'],headers=beta_h).status_code==404
    assert len(client.get(base,headers=alpha_h).json()['items'])==1


def test_fairrank_detects_identity_embedded_skill_as_proxy():
    check=identity_invariance('J’ai réalisé un portail pour une bibliothèque.',
        ['Claire Dupont','Angular Martin'],[('ang','angular','angular')])
    assert check['invariant'] is False
    assert 'biais' in ' '.join(check['limitations'])
