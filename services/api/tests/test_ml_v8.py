"""Phase ML+: contextual non-generative recognition, grounded section facts and calibration."""
import json
import math
import pytest
from sqlalchemy import select

from app.ml.recognition import extract_mentions, normalize
from app.ml.sections import section_lines, extract_source_facts
from app.ml.skill_rank import rank_labels
from app.ml.calibration import LabeledPair, calibrate
from app.ml.terminology import seed_glossary
from app.ml.processing import analyze_document
from app.core.database import get_db
from app.main import app
from app.models import DocumentFact, DocumentPage, SkillEvidence
from test_documents import FakeStorage, docx_bytes, create_batch, override_storage
from test_recruitment import auth_headers


@pytest.mark.parametrize('text,status,code', [
    ('No previous knowledge of Python.', 'needs_review', 'negated'),
    ('Sans expérience en Python.', 'needs_review', 'negated'),
    ("Je n'ai jamais utilisé Python.", 'needs_review', 'negated'),
    ('I want to learn Python.', 'needs_review', 'learning_only'),
    ('Interested in Python.', 'needs_review', 'hypothetical'),
    ('Python: beginner.', 'needs_review', 'negated'),
    ('J’utilise Python dans mes projets.', 'mentioned', 'lexical_observation_only'),
])
def test_context_rules(text, status, code):
    hit=extract_mentions(text,[('python','python','python')])[0]
    assert (hit.status,hit.context_code)==(status,code)
    assert text[hit.start:hit.end]==hit.mention


def test_job_requirements_not_evidence():
    src='Required skills\nAngular\nGit\nProjects\nDeveloped Angular components.'
    hits=extract_mentions(src,[('angular','angular','angular'),('git','git','git')])
    assert [(h.skill_id,h.status) for h in hits]==[
        ('angular','needs_review'),('git','needs_review'),('angular','mentioned')]
    assert hits[0].context_code=='section_requirements'


def test_source_grounded_facts_offsets():
    source='Education\nLicence en informatique — 2024\nProjects\nProjet de bibliothèque en Angular\nContact\nfoo@example.org'
    facts=extract_source_facts(source)
    assert [f.section for f in facts]==['education','projects']
    assert all(source[f.start:f.end]==f.text for f in facts)
    assert not any('@' in f.text for f in facts)


class FakeEmbedder:
    def __init__(self, mapping): self.mapping=mapping
    def encode(self, texts): return [self.mapping[t] for t in texts]


def test_embedding_skill_ranking_is_only_suggestion():
    result=rank_labels(FakeEmbedder({'backend':[1.,0.], 'Python':[0.9,0.1],
             'Supply chain':[0.,1.]}), 'backend', [('a','Python'),('b','Supply chain')])
    assert [r['skill_id'] for r in result]==['a','b']
    assert all(r['state']=='candidate_to_review' for r in result)
    assert all('probability' not in r for r in result)
    with pytest.raises(ValueError,match='INVALID_CATALOGUE'):
        rank_labels(FakeEmbedder({'backend':[1,0]}),'backend',[('a','Python'),('a','Python')])
    with pytest.raises(ValueError,match='INVALID_EMBEDDING'):
        rank_labels(FakeEmbedder({'backend':[1,0],'Python':[math.nan,0]}),'backend',[('a','Python')])


def sample_pairs():
    return [LabeledPair('a','train',0.92,True,'fr'),
            LabeledPair('b','train',0.88,True,'en'),
            LabeledPair('c','train',0.20,False,'fr'),
            LabeledPair('d','train',0.55,False,'en'),
            LabeledPair('e','validation',0.81,True,'fr'),
            LabeledPair('f','validation',0.10,False,'en')]


def test_calibrate_has_no_validation_leakage():
    report=calibrate(sample_pairs(),min_precision=1.0)
    assert report['selected']
    assert report['threshold']==0.88
    assert report['validation']['fn']==1  # unvalidated recall; no false success
    assert report['by_language']['fr']['fn']==1
    with pytest.raises(ValueError,match='DATA_LEAKAGE'):
        calibrate(sample_pairs()+[LabeledPair('a','validation',0.1,False,'fr')])
    with pytest.raises(ValueError,match='INVALID_ANNOTATIONS'):
        calibrate([*sample_pairs()[:-1],LabeledPair('f','validation',math.nan,False,'en')])


def test_ml_facts_and_context_endpoint_isolated(client_and_orgs, monkeypatch):
    client,_=client_and_orgs
    store=FakeStorage();override_storage(store,monkeypatch)
    db=next(app.dependency_overrides[get_db]())
    try:
        seed_glossary(db)
        headers=auth_headers(client)
        batch=create_batch(client,headers)
        cv=('Education\nLicence en informatique 2023\nProjects\n'
            'Application Angular et TypeScript pour une association.\n'
            'Skills\nSans expérience en Python.')
        response=client.post(f'/api/v1/uploads/batches/{batch}/files',headers=headers,
              files={'file':('preuve.docx',docx_bytes(cv))})
        assert response.status_code==201,response.text
        doc_id=response.json()['items'][0]['id']
        from app.documents.processing import process_document
        assert process_document(doc_id,db,store)=='completed'
        assert analyze_document(doc_id,db)=='completed'
        facts=client.get(f'/api/v1/documents/{doc_id}/nlp/facts',headers=headers)
        assert facts.status_code==200,facts.text
        sections={f['category'] for f in facts.json()['items']}
        assert 'education' in sections and 'projects' in sections
        pages=db.scalars(select(DocumentPage).where(DocumentPage.document_id==doc_id)).all()
        for fact in facts.json()['items']:
            page=next(p for p in pages if p.page_number==fact['page_number'])
            assert page.text[fact['start_offset']:fact['end_offset']]==fact['source_text']
        mention=client.get(f'/api/v1/documents/{doc_id}/nlp',headers=headers)
        hits=mention.json()['items']
        python=next(h for h in hits if h['skill_code']=='python')
        assert (python['status'],python['context_code'])==('needs_review','negated')
        count=db.query(DocumentFact).count()
        assert count==len(facts.json()['items'])
        assert analyze_document(doc_id,db)=='unchanged'
        # A second company may not read the newly extracted facts.
        from app.models import User, OrganizationMember
        from app.core.security import hash_password
        other=User(email='beta.ml@example.org',full_name='Beta Reviewer',
                   password_hash=hash_password('secret-pass-for-test-123'))
        db.add(other); db.flush()
        from app.models import Organization
        beta=db.scalar(select(Organization).where(Organization.slug=='beta'))
        db.add(OrganizationMember(user_id=other.id,organization_id=beta.id,role='org_admin'))
        db.commit()
        credentials=client.post('/api/v1/auth/login',json={
            'organization_slug':'beta','email':other.email,
            'password':'secret-pass-for-test-123'})
        assert credentials.status_code==200
        beta_headers={'Authorization':'Bearer '+credentials.json()['access_token']}
        assert client.get(f'/api/v1/documents/{doc_id}/nlp/facts',headers=beta_headers).status_code==404
    finally:
        db.close()


def test_semantic_suggestions_disabled_by_default(client_and_orgs):
    client,_=client_and_orgs
    answer=client.post('/api/v1/skills/semantic-suggestions',
                      json={'text':'API backend'},headers=auth_headers(client))
    assert answer.status_code==503


def test_semantic_suggestions_reauthorize_reference_ids(client_and_orgs,monkeypatch):
    from app.api.v1 import nlp
    from types import SimpleNamespace
    client,_=client_and_orgs
    db=next(app.dependency_overrides[get_db]())
    try:
        seed_glossary(db)
        from app.ml import remote
        monkeypatch.setattr(remote,'ml_request',lambda _endpoint,payload:{'items':[
            {'skill_id':'unknown','similarity':0.999},
            {'skill_id':payload['labels'][0]['skill_id'],'similarity':0.7}]})
        # local import at runtime -> monkeypatch settings function on config module
        import app.core.config as config
        monkeypatch.setattr(config,'get_settings',lambda:SimpleNamespace(
                  semantic_enabled=True,embedding_model='stub-encoder'))
        r=client.post('/api/v1/skills/semantic-suggestions',
                headers=auth_headers(client),json={'text':'backend web'})
        assert r.status_code==200,r.text
        assert len(r.json()['items'])==1
        assert r.json()['items'][0]['status']=='candidate_to_review'
    finally:db.close()


def test_supervised_ml_experiment_is_group_heldout():
    from app.ml.supervised import TrainingPair,train_and_evaluate
    train=[TrainingPair(f'train-{i}','train', 'développement python' if i%2 else 'inventory management',
            f'conçu API Python projet {i}' if i%2 else f'gestion terrain stock {i}',
            int(i%2), 'fr' if i%3 else 'en') for i in range(24)]
    val=[TrainingPair(f'val-{i}','validation', 'backend python' if i%2 else 'supply chain',
           f'API locale FastAPI test {i}' if i%2 else f'activités de stocks {i}',
           int(i%2), 'fr' if i%3 else 'en') for i in range(10)]
    estimator,report=train_and_evaluate(train+val)
    assert report['train_pairs']==24 and report['validation_pairs']==10
    assert 0<=report['heldout']['f1']<=1
    assert hasattr(estimator,'predict_proba')
    with pytest.raises(ValueError,match='GROUP_LEAKAGE'):
        train_and_evaluate(train+val+[TrainingPair('train-0','validation','different','different',1,'fr')])
    with pytest.raises(ValueError,match='DUPLICATE_PAIR_ACROSS_SPLITS'):
        train_and_evaluate(train+val+[TrainingPair('new-val','validation',train[0].requirement,
                                                 train[0].evidence,0,'en')])
