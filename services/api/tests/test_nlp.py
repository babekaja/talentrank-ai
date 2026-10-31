"""Phase 4: synthetic-only NLP behavior; no real applicant data."""
from sqlalchemy import select
from app.main import app
from app.core.database import get_db
from app.ml.terminology import seed_glossary
from app.ml.processing import analyze_document
from app.ml.recognition import extract_mentions, normalize
from app.models import CVDocument, DocumentPage, SkillEvidence, Skill
from app.models.auth import uid
from test_documents import FakeStorage, docx_bytes, create_batch, override_storage
from test_recruitment import auth_headers


def test_unicode_boundaries_and_uncertain_claims():
    aliases=[('angular',normalize('angular'),normalize('Angular')),
             ('python',normalize('python'),normalize('Python')),
             ('js',normalize('js'),normalize('JavaScript'))]
    text='Je maîtrise Angular. Sans expérience en Python. Je souhaite apprendre JS. AngularJS est distinct.'
    hits=extract_mentions(text,aliases)
    angular=[h for h in hits if h.skill_id=='angular']
    assert len(angular)==1 and angular[0].status=='mentioned'
    assert any(h.skill_id=='python' and h.status=='needs_review' for h in hits)
    assert any(h.skill_id=='js' and h.status=='needs_review' for h in hits)
    assert all(text[h.start:h.end]==h.mention for h in hits)
    assert not extract_mentions('Utilisation de logiciels sans développement backend',aliases)


def test_aliases_not_equivalent_to_related_skills(client_and_orgs):
    _client,_=client_and_orgs
    db=next(app.dependency_overrides[get_db]())
    try:
        seed_glossary(db)
        codes={s.code:s.id for s in db.scalars(select(Skill)).all()}
        assert {'html','css','rxjs','figma','web_accessibility','angular_material'} <= set(codes)
        assert codes['fastapi']!=codes['python']
        assert codes['docker']!=codes['git']
        assert db.scalars(select(Skill)).all()
        assert len({s.id for s in db.scalars(select(Skill)).all()})==len(codes)
        seed_glossary(db)
        assert len(db.scalars(select(Skill)).all())==len(codes)
    finally:db.close()


def test_api_real_document_nlp_review_isolation(client_and_orgs,monkeypatch):
    client,orgs=client_and_orgs
    store=FakeStorage();override_storage(store,monkeypatch)
    db=next(app.dependency_overrides[get_db]())
    try:
        seed_glossary(db)
        headers=auth_headers(client)
        bid=create_batch(client,headers)
        text='Projet: réalisation application Angular et TypeScript. Sans expérience en Python. API REST.'
        reply=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=headers,
                          files={'file':('profil.docx',docx_bytes(text))})
        assert reply.status_code==201,reply.text
        did=reply.json()['items'][0]['id']
        from app.documents.processing import process_document
        assert process_document(did,db,store)=='completed'
        assert analyze_document(did,db)=='completed'
        assert analyze_document(did,db)=='unchanged'
        response=client.get(f'/api/v1/documents/{did}/nlp',headers=headers)
        assert response.status_code==200,response.text
        body=response.json()
        assert body['state']=='completed'
        by_code={item['skill_code']:item for item in body['items']}
        for code in ('angular','typescript','python','rest_api'):
            assert code in by_code,body
        assert by_code['python']['status']=='needs_review'
        assert by_code['angular']['status']=='mentioned'
        assert 'Angular' in by_code['angular']['source_quote']
        assert len({r['id'] for r in body['items']})==len(body['items'])
        page=db.scalar(select(DocumentPage).where(DocumentPage.document_id==did))
        for item in body['items']:
            assert page.text[item['start_offset']:item['end_offset']]==item['matched_text']
        review=client.patch(f'/api/v1/documents/{did}/nlp/{by_code["angular"]["id"]}/review',
                  headers=headers,json={'decision':'confirmed'})
        assert review.status_code==200,review.text
        # Changing one unrelated alias triggers refresh, but human confirmation persists.
        from app.models import SkillAlias
        other=db.scalar(select(Skill).where(Skill.code=='python'))
        db.add(SkillAlias(skill_id=other.id,normalized_alias='py-lang-test',
                          provenance='test-suite',verified=True))
        db.commit()
        assert analyze_document(did,db)=='completed'
        refreshed=client.get(f'/api/v1/documents/{did}/nlp',headers=headers).json()['items']
        assert next(x for x in refreshed if x['skill_code']=='angular')['status']=='confirmed'
        assert client.get('/api/v1/skills',headers=headers).status_code==200
        wrong=client.get('/api/v1/documents/not-a-document/nlp',headers=headers)
        assert wrong.status_code==404
        assert client.patch(f'/api/v1/documents/{did}/nlp/random/review',headers=headers,
                            json={'decision':'confirmed'}).status_code==404
    finally:
        db.close();app.dependency_overrides.pop(__import__('app.documents.storage',fromlist=['get_storage']).get_storage,None)


def test_organization_aliases_admin_only_and_conflict(client_and_orgs):
    client,orgs=client_and_orgs
    db=next(app.dependency_overrides[get_db]())
    try:
        seed_glossary(db)
        h=auth_headers(client)
        skill=db.scalar(select(Skill).where(Skill.code=='inventory_management'))
        from app.models import OrganizationSkillAlias
        payload={'alias':'Gestion des inventaires locaux','language':'fr',
                 'justification':'Validation métier par le gestionnaire des stocks'}
        added=client.post(f'/api/v1/skills/{skill.id}/aliases',headers=h,json=payload)
        assert added.status_code==201,added.text
        listed=client.get(f'/api/v1/skills/{skill.id}/aliases',headers=h).json()['items']
        assert any(x['alias']=='gestion des inventaires locaux' for x in listed)
        assert client.post(f'/api/v1/skills/{skill.id}/aliases',headers=h,json=payload).status_code==409
        entry=db.scalar(select(OrganizationSkillAlias).where(OrganizationSkillAlias.skill_id==skill.id))
        assert entry.organization_id==orgs['alpha']
        assert entry.justification==payload['justification']
        assert client.post(f'/api/v1/skills/{skill.id}/aliases',headers=h,json={
            **payload,'justification':'non'}).status_code==422
    finally:db.close()


def test_homonym_alias_stays_uncertain():
    text='Conception de logiciels avec le langage ABC.'
    pairs=[('skill_one','abc','alpha'),('skill_two','abc','beta')]
    results=extract_mentions(text,pairs)
    assert len(results)==2
    assert all(h.status=='needs_review' for h in results)


def test_vector_chunks_preserve_exact_spans():
    from app.ml.vectors import chunks, semantic_collection
    source='Développement Angular.\n'+('Gestion de projet et API REST. '*70)
    result=chunks(source,180)
    assert result and len(result)>3
    assert ''.join(chunk for _,_,chunk in result)==source
    assert all(source[start:end]==chunk for start,end,chunk in result)
    assert semantic_collection('BAAI/bge-m3')!=semantic_collection('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')


def test_semantic_feature_disabled_explicitly(client_and_orgs):
    client,_=client_and_orgs
    h=auth_headers(client)
    result=client.post('/api/v1/semantic/search',headers=h,json={'query':'Angular API REST'})
    assert result.status_code==503
    assert 'non activée' in result.text


def test_semantic_search_never_trusts_qdrant_for_authorization(client_and_orgs,monkeypatch):
    # Even a poisoned Qdrant answer containing an ID from another tenant is discarded.
    from app.api.v1 import semantic
    from types import SimpleNamespace
    client,orgs=client_and_orgs
    fake=FakeStorage();override_storage(fake,monkeypatch)
    db=next(app.dependency_overrides[get_db]())
    try:
        h=auth_headers(client)
        bid=create_batch(client,h)
        response=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,
                             files={'file':('private.docx',docx_bytes('Angular Python'))})
        did=response.json()['items'][0]['id']
        from app.documents.processing import process_document
        assert process_document(did,db,fake)=='completed'
        page=db.scalar(select(DocumentPage).where(DocumentPage.document_id==did))
        monkeypatch.setattr(semantic,'get_settings',lambda:SimpleNamespace(semantic_enabled=True,embedding_model='fake-test'))
        monkeypatch.setattr(semantic,'ml_request',lambda path,payload:{'items':[
            {'document_id':did,'page_id':page.id,'start':0,'end':7,'similarity':0.99}]})
        from app.models import User, OrganizationMember
        from app.core.security import hash_password
        beta=User(email='beta.semantic@example.org',full_name='Recruteur Beta',
                  password_hash=hash_password('password-beta-123'))
        db.add(beta);db.flush()
        db.add(OrganizationMember(user_id=beta.id,organization_id=orgs['beta'],role='org_admin'))
        db.commit()
        token=client.post('/api/v1/auth/login',json={
            'organization_slug':'beta','email':'beta.semantic@example.org',
            'password':'password-beta-123'}).json()['access_token']
        bh={'Authorization':f'Bearer {token}'}
        result=client.post('/api/v1/semantic/search',headers=bh,json={'query':'Angular'})
        assert result.status_code==200,result.text
        assert result.json()['items']==[]
        own=client.post('/api/v1/semantic/search',headers=h,json={'query':'Angular'})
        assert own.status_code==200
        assert own.json()['items'][0]['excerpt']==page.text[:7]
        assert own.json()['items'][0]['status']=='retrieval_only'
    finally:db.close()


def test_official_esco_csv_import_stays_inactive(client_and_orgs,tmp_path):
    from scripts.import_esco import import_esco
    import csv
    inputfile=tmp_path/'skills_fr.csv'
    with inputfile.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['conceptUri','preferredLabel','conceptType'])
        writer.writeheader()
        writer.writerow({'conceptUri':'http://data.europa.eu/esco/skill/00000000-aaaa-bbbb-cccc-000000000001',
                         'preferredLabel':'Test de compétence fictive','conceptType':'skill'})
        writer.writerow({'conceptUri':'http://data.europa.eu/esco/occupation/fake',
                         'preferredLabel':'Profession fictive','conceptType':'occupation'})
    db=next(app.dependency_overrides[get_db]())
    try:
        created,seen=import_esco(inputfile,'1.2.1','fr',db)
        assert (created,seen)==(1,1)
        skill=db.scalar(select(Skill).where(Skill.taxonomy=='esco'))
        assert skill and not skill.active and skill.version=='1.2.1'
    finally:db.close()
