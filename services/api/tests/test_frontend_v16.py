"""Real API contract tests for the Angular v16 workflows, all scoped by tenant."""
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import OrganizationMember, User
from test_recruitment import auth_headers, new_job, requirements


def _login(client, email, password, tenant='alpha'):
    res = client.post('/api/v1/auth/login', json={
        'organization_slug': tenant, 'email': email, 'password': password})
    assert res.status_code == 200, res.text
    return {'Authorization': 'Bearer ' + res.json()['access_token']}


def _setup(client, ids):
    admin_h = auth_headers(client)
    job_id = new_job(client, admin_h).json()['id']
    assert client.put(f'/api/v1/jobs/{job_id}/requirements', headers=admin_h,
                      json=requirements()).status_code == 200
    assert client.post(f'/api/v1/jobs/{job_id}/requirements/confirm', headers=admin_h,
                       json={'expected_version': 1}).status_code == 200
    campaign_id = client.post('/api/v1/campaigns', headers=admin_h,
                              json={'name': 'Équipe Mobile', 'job_id': job_id}).json()['id']
    assert client.patch(f'/api/v1/campaigns/{campaign_id}/status', headers=admin_h,
                        json={'status': 'active'}).status_code == 200
    candidate = client.post('/api/v1/candidates', headers=admin_h,
                            json={'full_name': 'Nom Confidentiel', 'email': 'private@example.org'}).json()
    application_id = client.post('/api/v1/applications', headers=admin_h,
                                 json={'candidate_id': candidate['id'],
                                       'campaign_id': campaign_id}).json()['id']
    with next(app.dependency_overrides[get_db]()) as db:
        reviewer = User(email='evaluator@alpha.example.org', full_name='Examinateur',
                        password_hash=hash_password('secure-evaluator-password'))
        other = User(email='evaluator@beta.example.org', full_name='Examinateur Beta',
                     password_hash=hash_password('secure-beta-password'))
        db.add_all([reviewer, other]); db.flush()
        member = OrganizationMember(user_id=reviewer.id, organization_id=ids['alpha'], role='evaluator')
        foreign = OrganizationMember(user_id=other.id, organization_id=ids['beta'], role='evaluator')
        db.add_all([member, foreign]); db.commit()
        member_id, foreign_id = member.id, foreign.id
    evaluator_h = _login(client, 'evaluator@alpha.example.org', 'secure-evaluator-password')
    beta_h = _login(client, 'evaluator@beta.example.org', 'secure-beta-password', 'beta')
    return admin_h, evaluator_h, beta_h, application_id, member_id, foreign_id, candidate['id']


def test_evaluator_access_assignment_and_independent_review(client_and_orgs):
    client, ids = client_and_orgs
    ah, eh, bh, aid, mid, foreign, candidate = _setup(client, ids)
    assert client.get('/api/v1/evaluator/assignments', headers=eh).json()['total'] == 0
    assert client.get('/api/v1/applications', headers=eh).status_code == 403
    assert client.post('/api/v1/evaluator/assignments', headers=eh, json={
        'application_id': aid, 'evaluator_member_id': mid}).status_code == 403
    assert client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': foreign}).status_code == 404
    r = client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': mid})
    assert r.status_code == 201, r.text
    assignment_id = r.json()['id']
    assert 'full_name' not in r.json() and 'email' not in r.json()
    assert client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': mid}).status_code == 409
    assert client.get('/api/v1/evaluator/assignments', headers=eh).json()['total'] == 1
    assert client.get(f'/api/v1/evaluator/assignments/{assignment_id}', headers=bh).status_code == 404
    evidence = client.get(f'/api/v1/evaluator/assignments/{assignment_id}/evidence', headers=eh)
    assert evidence.status_code == 200 and evidence.json()['items'] == []
    assert client.get(f'/api/v1/evaluator/assignments/{assignment_id}/evidence', headers=ah).status_code == 403
    review = client.post(f'/api/v1/evaluator/assignments/{assignment_id}/reviews', headers=eh,
                         json={'finding': 'needs_clarification', 'note': 'Vérifier la durée du stage.'})
    assert review.status_code == 201, review.text
    assert client.post(f'/api/v1/evaluator/assignments/{assignment_id}/reviews', headers=eh,
                       json={'finding': 'shortlisted', 'note': 'Une seconde décision.'}).status_code == 409
    from app.models import Application
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.get(Application, aid).review_status == 'to_review'
    assert client.post(f'/api/v1/evaluator/assignments/{assignment_id}/revoke', headers=ah).status_code == 200
    assert client.get('/api/v1/evaluator/assignments', headers=eh).json()['total'] == 0
    assert client.get(f'/api/v1/evaluator/assignments/{assignment_id}', headers=eh).status_code == 404
    assert client.post(f'/api/v1/evaluator/assignments/{assignment_id}/reviews', headers=eh,
                       json={'finding':'reviewed','note':'Non autorisé.'}).status_code == 404


def test_evaluator_role_changed_and_reassignment(client_and_orgs):
    client, ids = client_and_orgs
    ah, eh, _, aid, mid, _, _ = _setup(client, ids)
    first = client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': mid}).json()
    client.post(f'/api/v1/evaluator/assignments/{first["id"]}/revoke', headers=ah)
    again = client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': mid})
    assert again.status_code == 201 and again.json()['id'] == first['id']
    patch = client.patch(f'/api/v1/members/{mid}', headers=ah, json={'role':'recruiter'})
    assert patch.status_code == 200
    # Existing JWT may be revalidated as recruiter; it must not be allowed to see evaluator's case.
    assert client.get('/api/v1/evaluator/assignments', headers=eh).status_code in (200, 403)
    assert client.get(f'/api/v1/evaluator/assignments/{first["id"]}/evidence', headers=eh).status_code == 403


def test_training_catalog_crud_verify_isolation(client_and_orgs):
    client, ids = client_and_orgs
    ah, eh, bh, aid, mid, foreign, candidate = _setup(client, ids)
    assert client.get('/api/v1/training-courses', headers=eh).status_code == 403
    content = {'title':'Cours public Angular', 'provider':'Centre de formation',
               'official_url':'https://example.org/courses/angular', 'language':'fr',
               'level':'intermédiaire', 'skill_id': None,
               'description':'Référence à vérifier manuellement.'}
    assert client.post('/api/v1/training-courses', headers=ah,
                       json={**content,'official_url':'javascript:alert(1)'}).status_code == 422
    created = client.post('/api/v1/training-courses', headers=ah, json=content)
    assert created.status_code == 201, created.text
    cid = created.json()['id']
    assert created.json()['verified_at'] is None
    assert client.get('/api/v1/training-courses', headers=ah).json()['total'] == 1
    assert client.get('/api/v1/training-courses', headers=ah, params={'q':'nothing'}).json()['total'] == 0
    assert client.get('/api/v1/training-courses', headers=bh).status_code == 403
    assert client.post(f'/api/v1/training-courses/{cid}/verify', headers=ah,
                       json={'source_checked':False}).status_code == 422
    good = client.post(f'/api/v1/training-courses/{cid}/verify', headers=ah,
                       json={'source_checked':True})
    assert good.status_code == 200 and good.json()['verified_at']
    updated = client.put(f'/api/v1/training-courses/{cid}', headers=ah,
                         json={**content,'title':'Cours Angular révisé'})
    assert updated.status_code == 200 and updated.json()['verified_at'] is None
    assert client.delete(f'/api/v1/training-courses/{cid}', headers=ah).status_code == 200
    assert client.get('/api/v1/training-courses', headers=ah).json()['total'] == 0
    assert client.put(f'/api/v1/training-courses/{cid}', headers=ah, json=content).status_code == 409


def test_cross_org_admin_cannot_access_others_courses_and_assignments(client_and_orgs):
    client, ids = client_and_orgs
    ah, eh, _, aid, mid, _, _ = _setup(client, ids)
    with next(app.dependency_overrides[get_db]()) as db:
        beta = User(email='admin@beta.example.org', full_name='Beta Admin',
                    password_hash=hash_password('beta-admin-good-pass'))
        db.add(beta); db.flush()
        db.add(OrganizationMember(user_id=beta.id, organization_id=ids['beta'], role='org_admin'))
        db.commit()
    beta_h = _login(client, 'admin@beta.example.org', 'beta-admin-good-pass', 'beta')
    asg = client.post('/api/v1/evaluator/assignments', headers=ah, json={
        'application_id': aid, 'evaluator_member_id': mid}).json()
    c = client.post('/api/v1/training-courses', headers=ah, json={
        'title':'Cours SQL','provider':'Institut public',
        'official_url':'https://example.org/sql','language':'en','level':'basic'}).json()
    assert client.get('/api/v1/evaluator/assignments', headers=beta_h).json()['total'] == 0
    assert client.get(f'/api/v1/evaluator/assignments/{asg["id"]}', headers=beta_h).status_code == 404
    assert client.post(f'/api/v1/evaluator/assignments/{asg["id"]}/revoke', headers=beta_h).status_code == 404
    assert client.get('/api/v1/training-courses', headers=beta_h).json()['total'] == 0
    assert client.put(f'/api/v1/training-courses/{c["id"]}', headers=beta_h, json={
        'title':'Cours SQL','provider':'Institut public',
        'official_url':'https://example.org/sql','language':'en','level':'basic'}).status_code == 404
    assert client.delete(f'/api/v1/training-courses/{c["id"]}', headers=beta_h).status_code == 404


def test_erasure_clears_assignment_and_assignment_audit(client_and_orgs):
    from app.documents.storage import get_storage
    from app.models import ApplicationAssignment, AuditLog
    from test_privacy import Storage, setup_candidate
    from sqlalchemy import select
    client, ids = client_and_orgs
    admin = auth_headers(client)
    _, candidate_id, application_id = setup_candidate(client, admin, ids['alpha'])
    with next(app.dependency_overrides[get_db]()) as db:
        user = User(email='erasure-reviewer@alpha.example.org', full_name='Review Test',
                    password_hash=hash_password('long-secure-password'))
        db.add(user); db.flush()
        member = OrganizationMember(user_id=user.id, organization_id=ids['alpha'], role='evaluator')
        db.add(member); db.commit()
        mid = member.id
    assigned = client.post('/api/v1/evaluator/assignments', headers=admin, json={
        'application_id': application_id, 'evaluator_member_id': mid})
    assert assigned.status_code == 201
    assignment_id = assigned.json()['id']
    app.dependency_overrides[get_storage] = lambda: Storage()
    try:
        erased = client.post(f'/api/v1/privacy/candidates/{candidate_id}/erase', headers=admin,
                             json={'confirmation':'SUPPRIMER'})
        assert erased.status_code == 200, erased.text
        with next(app.dependency_overrides[get_db]()) as db:
            assert db.get(ApplicationAssignment, assignment_id) is None
            assert db.scalar(select(AuditLog).where(AuditLog.resource_id == assignment_id)) is None
    finally:
        app.dependency_overrides.pop(get_storage, None)


def test_paged_assignable_applications_and_enriched_list(client_and_orgs):
    client, ids = client_and_orgs
    ah, eh, _, aid, mid, _, candidate = _setup(client, ids)
    page = client.get('/api/v1/evaluator/assignable-applications', headers=ah, params={'limit':1})
    assert page.status_code == 200 and page.json()['total'] == 1
    assert page.json()['items'][0]['application_id'] == aid
    assert 'full_name' not in page.json()['items'][0]
    assert client.get('/api/v1/evaluator/assignable-applications', headers=eh).status_code == 403
    assert client.get('/api/v1/evaluator/assignable-applications', headers=ah,
                      params={'q':'not-a-reference'}).json()['total'] == 0
    app_list = client.get('/api/v1/applications', headers=ah, params={'limit':1})
    assert app_list.status_code == 200 and app_list.json()['total'] == 1
    item = app_list.json()['items'][0]
    assert item['candidate_name'] == 'Nom Confidentiel'
    assert item['candidate_reference'].startswith('TR-')
    assert item['campaign_name'] == 'Équipe Mobile'
    assert client.get('/api/v1/applications', headers=eh).status_code == 403
