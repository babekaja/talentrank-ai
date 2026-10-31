"""API smoke path with actual SQLAlchemy/SQLite and synthetic CV (storage/queue stubbed).

This does NOT replace the Docker/MySQL/Redis/MinIO integration test.
"""
from sqlalchemy import select
from app.main import app
from app.core.database import get_db
from app.models import Skill
from app.ml.terminology import seed_glossary
from app.documents.processing import process_document
from app.ml.processing import analyze_document
from app.ml.matching_service import execute_matching_run
from test_documents import FakeStorage, docx_bytes, override_storage
from test_recruitment import auth_headers, new_job


def test_full_backend_recruitment_path(client_and_orgs, monkeypatch):
    client,_=client_and_orgs
    store=FakeStorage()
    override_storage(store, monkeypatch)
    from app.api.v1 import matching as matching_api
    monkeypatch.setattr(matching_api,'enqueue_matching',lambda _id:None)
    try:
        headers=auth_headers(client)
        with next(app.dependency_overrides[get_db]()) as db:
            seed_glossary(db)
            codes={s.code:s.id for s in db.scalars(select(Skill)).all()}
        job=new_job(client,headers)
        assert job.status_code==201
        jid=job.json()['id']
        criteria={'items':[
            {'code':'angular','label':'Angular','category':'skill','required':True,
             'weight':1,'justification':'Projets Web','skill_ref':codes['angular']},
            {'code':'diploma','label':'Diplôme vérifiable','category':'qualification','required':False,
             'weight':1,'justification':'Évaluation par une personne'},
        ]}
        assert client.put(f'/api/v1/jobs/{jid}/requirements',json=criteria,headers=headers).status_code==200
        assert client.post(f'/api/v1/jobs/{jid}/requirements/confirm',json={'expected_version':1},headers=headers).status_code==200
        camp=client.post('/api/v1/campaigns',json={'name':'Parcours synthétique','job_id':jid},headers=headers)
        assert camp.status_code==201
        cid=camp.json()['id']
        assert client.patch(f'/api/v1/campaigns/{cid}/status',json={'status':'active'},headers=headers).status_code==200
        batch=client.post('/api/v1/uploads/batches',json={'campaign_id':cid},headers=headers)
        assert batch.status_code==201
        upload=client.post(f'/api/v1/uploads/batches/{batch.json()["id"]}/files',headers=headers,
                           files={'file':('candidat-synthetique.docx', docx_bytes('Projet Angular et TypeScript.'))})
        assert upload.status_code==201
        did=upload.json()['items'][0]['id']
        with next(app.dependency_overrides[get_db]()) as db:
            assert process_document(did,db,store)=='completed'
            assert analyze_document(did,db)=='completed'
        ev=client.get(f'/api/v1/documents/{did}/viewer',headers=headers)
        assert ev.status_code==200,ev.text
        assert ev.json()['pages']
        run=client.post(f'/api/v1/jobs/{jid}/matching-runs',params={'campaign_id':cid},headers=headers)
        assert run.status_code==202,run.text
        rid=run.json()['id']
        with next(app.dependency_overrides[get_db]()) as db:
            assert execute_matching_run(rid,db)=='completed'
        results=client.get(f'/api/v1/matching-runs/{rid}/results',headers=headers)
        assert results.status_code==200,results.text
        assert results.json()['total']==1
        item=results.json()['items'][0]
        assert item['state']=='partial_review_required' and item['score'] is None
        assert item['group_coverage']['summary']['evaluable_subset_coverage']==100
        explanation=client.get(f'/api/v1/matching-results/{item["id"]}/explanation',headers=headers)
        assert explanation.status_code==200, explanation.text
        assert not explanation.json()['stale']
        assert any(c['evidence'] for c in explanation.json()['criteria'])
        assert client.post(f'/api/v1/matching-results/{item["id"]}/request-review',headers=headers).status_code==201
        exported=client.get(f'/api/v1/reports/campaigns/{cid}',headers=headers,params={'format':'csv','run_id':rid})
        assert exported.status_code==200
        assert 'Non calculable' in exported.content.decode('utf-8-sig')
        assert client.get('/api/v1/reports/history',headers=headers).json()['items']
        assert client.get('/api/v1/audit-logs',headers=headers).status_code==200
    finally:
        from app.documents.storage import get_storage
        app.dependency_overrides.pop(get_storage,None)
