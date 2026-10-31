"""Résolution exacte des critères sans modifier les campagnes validées."""
from sqlalchemy import select

from app.main import app
from app.core.database import get_db
from app.ml.matching_service import resolve_skills
from app.ml.terminology import seed_glossary
from app.models import Job, Skill, SkillAlias, OrganizationSkillAlias, OrganizationMember
from app.models.auth import utcnow
from test_recruitment import auth_headers, new_job


def requirement(label, *, code='BACKEND_REQ_1', reference=None, category='skill'):
    return {'id':code,'code':code,'label':label,'category':category,'required':True,
            'weight':3,'justification':'Critère professionnel du poste backend','skill_ref':reference}


def test_exact_labels_and_verified_aliases_for_internal_codes(client_and_orgs):
    with next(app.dependency_overrides[get_db]()) as db:
        seed_glossary(db)
        skills={skill.code:skill.id for skill in db.scalars(select(Skill)).all()}
        mapping=resolve_skills(db,[requirement('Python'),requirement('API REST',code='BACKEND_REQ_2'),
            requirement('  FastAPI  ',code='BACKEND_REQ_3'),requirement('REST API development',code='BACKEND_REQ_4'),
            requirement('Python et FastAPI',code='BACKEND_REQ_5'),requirement('Redis',code='BACKEND_REQ_6')])
        assert list(mapping.values())==[skills['python'],skills['rest_api'],skills['fastapi'],skills['rest_api'],None,None]


def test_explicit_references_inactive_ambiguous_and_unverified_labels(client_and_orgs):
    _,orgs=client_and_orgs
    with next(app.dependency_overrides[get_db]()) as db:
        seed_glossary(db)
        python=db.scalar(select(Skill).where(Skill.code=='python'))
        git=db.scalar(select(Skill).where(Skill.code=='git'))
        db.add_all([
            SkillAlias(skill_id=python.id,normalized_alias='libelle partage',verified=True,provenance='test'),
            SkillAlias(skill_id=git.id,normalized_alias='libelle partage',verified=True,provenance='test'),
            SkillAlias(skill_id=python.id,normalized_alias='alias non valide',verified=False,provenance='test'),
        ])
        member=db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==orgs['alpha']))
        db.add(OrganizationSkillAlias(organization_id=orgs['beta'],skill_id=python.id,
            normalized_alias='alias entreprise etrangere',language='fr',justification='Alias de test isolé',
            reviewed_by=member.user_id,reviewed_at=utcnow(),version=1))
        db.commit()
        assert resolve_skills(db,[requirement('Python',reference='inconnue')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('libelle partage')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('alias non valide')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('alias entreprise etrangere')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('Python',category='experience')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('Python',reference=git.id)])['BACKEND_REQ_1']==git.id
        python.active=False;db.commit()
        assert resolve_skills(db,[requirement('Python')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('Python',reference=python.id)])['BACKEND_REQ_1'] is None


def test_punctuation_does_not_merge_distinct_technologies(client_and_orgs):
    with next(app.dependency_overrides[get_db]()) as db:
        c=Skill(code='c',label_fr='C',label_en='C',taxonomy='test',version='1')
        db.add(c);db.flush()
        db.add(SkillAlias(skill_id=c.id,normalized_alias='c',verified=True,provenance='test'))
        db.commit()
        assert resolve_skills(db,[requirement('C++')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('C#')])['BACKEND_REQ_1'] is None
        assert resolve_skills(db,[requirement('C')])['BACKEND_REQ_1']==c.id


def test_matching_starts_for_confirmed_backend_with_internal_codes(client_and_orgs,monkeypatch):
    client,orgs=client_and_orgs
    with next(app.dependency_overrides[get_db]()) as db:
        seed_glossary(db)
    headers=auth_headers(client)
    job=new_job(client,headers).json()
    labels=['Python','FastAPI','SQL','API REST','Docker','Git','MySQL','PostgreSQL','Redis','pytest','Linux','architecture logicielle']
    items=[{key:value for key,value in requirement(label,code=f'BACKEND_REQ_{i}').items() if key!='id'}
           for i,label in enumerate(labels,1)]
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements',headers=headers,json={'items':items}).status_code==200
    assert client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm',headers=headers,json={'expected_version':1}).status_code==200
    campaign=client.post('/api/v1/campaigns',headers=headers,json={'job_id':job['id'],'name':'Campagne backend test'}).json()
    assert client.patch(f'/api/v1/campaigns/{campaign["id"]}/status',headers=headers,json={'status':'active'}).status_code==200
    candidate=client.post('/api/v1/candidates',headers=headers,json={'full_name':'Profil fictif backend'}).json()
    assert client.post('/api/v1/applications',headers=headers,json={'campaign_id':campaign['id'],'candidate_id':candidate['id']}).status_code==201
    detail=client.get(f'/api/v1/jobs/{job["id"]}',headers=headers).json()
    assert sum(bool(req['resolved_skill_id']) for req in detail['requirements'])==8
    assert all(req['skill_ref'] is None for req in detail['requirements'])
    from app.api.v1 import matching
    monkeypatch.setattr(matching,'enqueue_matching',lambda _:None)
    started=client.post(f'/api/v1/jobs/{job["id"]}/matching-runs',headers=headers,params={'campaign_id':campaign['id']})
    assert started.status_code==202,started.text
    assert started.json()['mapping']['mapped']==8
    assert started.json()['mapping']['unmapped']==4
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements',headers=headers,json={'items':items}).status_code==409
    with next(app.dependency_overrides[get_db]()) as db:
        saved=db.get(Job,job['id'])
        assert saved.criteria_version==1 and saved.criteria_confirmed_at is not None
