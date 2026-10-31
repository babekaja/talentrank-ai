"""Regression coverage for bugs found in the independent v26 audit."""
from datetime import timedelta
import io
import zipfile

from app.api.v1 import candidate_portal, privacy, uploads
from app.core.database import get_db
from app.main import app
from app.models import (Candidate, CandidateContact, CandidateConsentEvent,
    CandidatePortalSession, CandidatePortalToken, Organization)
from app.models.auth import utcnow
from app.services.privacy import purge_candidate
from test_recruitment import auth_headers, new_job, requirements
from sqlalchemy import select


def _db():
    return next(app.dependency_overrides[get_db]())


def test_due_candidates_scans_beyond_first_500(client_and_orgs, monkeypatch):
    client, ids = client_and_orgs
    headers = auth_headers(client)
    old = utcnow() - timedelta(days=420)
    with _db() as db:
        batch = [Candidate(organization_id=ids['alpha'], reference=f'TEST-{i:04d}',
                           full_name=f'Candidat {i}', created_at=old + timedelta(seconds=i))
                 for i in range(525)]
        db.add_all(batch)
        db.commit()
    # The first 510 records cannot be erased; the last 15 can.
    def fake_plan(db, org, cid):
        item = db.get(Candidate, cid)
        return {'hold': int(item.reference.split('-')[1]) < 510,
                'applications': [], 'documents': [], 'document_ids': set()}
    monkeypatch.setattr(privacy, 'candidate_plan', fake_plan)
    response = client.get('/api/v1/privacy/candidates/due', headers=headers,
                          params={'limit': 10})
    assert response.status_code == 200, response.text
    assert [item['reference'] for item in response.json()['items']] == [f'TEST-{i:04d}' for i in range(510,520)]


def test_disabled_tenant_revokes_portal_session_and_challenge(client_and_orgs, monkeypatch):
    client, ids = client_and_orgs
    headers = auth_headers(client)
    candidate = client.post('/api/v1/candidates', json={
        'full_name':'Owner', 'email':'owner@example.org'},headers=headers).json()
    codes=[]
    monkeypatch.setattr(candidate_portal,'require_portal_enabled',lambda:None)
    monkeypatch.setattr(candidate_portal,'deliver_candidate_code',lambda email,code:codes.append(code))
    send=f'/api/v1/candidate-portal/candidates/{candidate["id"]}/send-access-code'
    assert client.post(send, headers=headers).status_code == 202
    code=codes[0]
    verified=client.post('/api/v1/candidate-portal/verify',json={'code':code})
    assert verified.status_code == 200
    secret=verified.json()['access_token']
    with _db() as db:
        org=db.get(Organization,ids['alpha']); org.is_active=False; db.commit()
    assert client.get('/api/v1/candidate-portal/me',headers={
        'Authorization':'Bearer '+secret}).status_code == 401
    # Replaying or using a still-unused code after org deactivation is forbidden.
    with _db() as db:
        active = db.scalar(select(CandidatePortalToken).where(
            CandidatePortalToken.candidate_id==candidate['id']))
        active.used_at=None
        db.commit()
    assert client.post('/api/v1/candidate-portal/verify',json={'code':code}).status_code==401


def test_erasure_removes_candidate_portal_data_without_fk_cascade(client_and_orgs):
    client, ids=client_and_orgs
    headers=auth_headers(client)
    cid=client.post('/api/v1/candidates', json={'full_name':'Delete me'},headers=headers).json()['id']
    with _db() as db:
        db.add_all([
            CandidatePortalToken(candidate_id=cid,organization_id=ids['alpha'],
                email_fingerprint='a'*64,challenge_hash='b'*64,expires_at=utcnow()+timedelta(days=1)),
            CandidatePortalSession(candidate_id=cid,organization_id=ids['alpha'],
                access_hash='c'*64,expires_at=utcnow()+timedelta(days=1)),
            CandidateConsentEvent(candidate_id=cid,organization_id=ids['alpha'],
                purpose='training_suggestions',action='granted',notice_version='training-suggestions-fr-v1',
                source='candidate_portal'),
        ])
        db.commit()
    class Storage:
        def delete(self,key): raise AssertionError('No documents stored')
    with _db() as db:
        from app.core.security import active_principal
        # Retrieve actor from the session to exercise the real service.
        from app.models import OrganizationMember, UserSession
        member=db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==ids['alpha']))
        session=db.scalar(select(UserSession).where(UserSession.organization_id==ids['alpha']))
        actor=active_principal(db, member.user_id, ids['alpha'], session.id)
        assert purge_candidate(db,actor,cid,Storage())['deleted'] is True
    with _db() as db:
        for model in (CandidatePortalToken,CandidatePortalSession,CandidateConsentEvent,Candidate):
            assert db.scalar(select(model).where(model.candidate_id==cid if model is not Candidate else model.id==cid)) is None


def test_zip_mixed_outcome_is_reported_not_misrepresented(client_and_orgs, monkeypatch):
    client, ids = client_and_orgs
    headers = auth_headers(client)
    job = new_job(client,headers).json()
    client.put(f'/api/v1/jobs/{job["id"]}/requirements',headers=headers,json=requirements())
    client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm',headers=headers,json={'expected_version':1})
    campaign = client.post('/api/v1/campaigns',headers=headers,json={'job_id':job['id'],'name':'Test ZIP'}).json()
    client.patch(f'/api/v1/campaigns/{campaign["id"]}/status',headers=headers,json={'status':'active'})
    batch=client.post('/api/v1/uploads/batches',headers=headers,json={'campaign_id':campaign['id']}).json()
    class Storage:
        def ensure_bucket(self):pass
    from app.documents.storage import get_storage
    app.dependency_overrides[get_storage]=lambda:Storage()
    from fastapi import HTTPException
    def fake_ingest(path,name,*args):
        if name=='bad.docx':raise HTTPException(422,'Format refusé')
        return {'id':'ok','filename':name,'status':'pending','queued':True}
    monkeypatch.setattr(uploads,'ingest',fake_ingest)
    # Deterministic local ZIP entries; valid contents are sufficient after replacing ingest.
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('good.docx',b'good document content')
        z.writestr('bad.docx',b'bad document content')
    try:
        r=client.post(f'/api/v1/uploads/batches/{batch["id"]}/files',headers=headers,
            files={'file':('files.zip',f.getvalue(),'application/zip')})
        assert r.status_code==207,r.text
        assert r.json()['accepted']==1 and r.json()['rejected']==1
        assert r.json()['failures'][0]['filename']=='bad.docx'
        assert r.json()['items'][0]['filename']=='good.docx'
    finally:
        app.dependency_overrides.pop(get_storage,None)


def test_partial_matching_order_is_mysql_compatible():
    from sqlalchemy import case, select
    from sqlalchemy.dialects import mysql
    from app.models import MatchingResult
    visible=case((MatchingResult.state=='documentary_coverage',MatchingResult.score),else_=None)
    statement=select(MatchingResult).order_by(visible.is_(None),visible.desc(),MatchingResult.application_id)
    sql=str(statement.compile(dialect=mysql.dialect()))
    assert 'NULLS LAST' not in sql  # unsupported in MySQL 8
    assert 'IS NULL' in sql and 'DESC' in sql
