from app.models import OrganizationMember, User
from app.core.security import hash_password
from app.core.database import get_db
from app.main import app
from test_auth import authenticate


def auth_headers(client):
    token = authenticate(client).json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def new_job(client, headers):
    return client.post('/api/v1/jobs', headers=headers, json={
        'title': 'Développeur Angular Python',
        'description': 'Créer et maintenir des applications web et des API sécurisées.',
        'work_mode': 'hybrid', 'opens_on': '2026-10-10', 'closes_on': '2026-11-10'
    })


def requirements():
    return {'items': [
        {'code': 'ANGULAR', 'label': 'Angular', 'category': 'skill', 'required': True,
         'weight': 5, 'justification': 'Application frontend métier'},
        {'code': 'REST', 'label': 'API REST', 'category': 'skill', 'required': False,
         'weight': 2, 'justification': 'Collaboration avec le backend'}
    ]}


def test_jobs_criteria_campaign_and_reviews(client_and_orgs):
    client, ids = client_and_orgs
    headers = auth_headers(client)
    result = new_job(client, headers)
    assert result.status_code == 201, result.text
    assert client.get('/api/v1/jobs', headers=headers, params={'q':'Angular'}).json()['total'] == 1
    assert client.get('/api/v1/jobs', headers=headers, params={'q':'DoesNotExist'}).json()['total'] == 0
    job_id = result.json()['id']
    assert result.json()['criteria_confirmed_at'] is None
    assert client.post('/api/v1/campaigns', headers=headers,
                       json={'name': 'Vague 1', 'job_id': job_id}).status_code == 409
    set_req = client.put(f'/api/v1/jobs/{job_id}/requirements', headers=headers,
                         json=requirements())
    assert set_req.status_code == 200, set_req.text
    assert set_req.json()['criteria_version'] == 1
    assert client.post(f'/api/v1/jobs/{job_id}/requirements/confirm', headers=headers,
                       json={'expected_version': 0}).status_code == 422
    confirmed = client.post(f'/api/v1/jobs/{job_id}/requirements/confirm', headers=headers,
                            json={'expected_version': 1})
    assert confirmed.status_code == 200, confirmed.text
    campaign = client.post('/api/v1/campaigns', headers=headers,
                           json={'name': 'Vague 1', 'job_id': job_id})
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()['id']
    assert client.get('/api/v1/campaigns', headers=headers, params={'q':'Vague'}).json()['total'] == 1
    assert client.get('/api/v1/campaigns', headers=headers, params={'q':'DoesNotExist'}).json()['total'] == 0
    assert client.get(f'/api/v1/campaigns/{campaign_id}', headers=headers).json()['name'] == 'Vague 1'
    active = client.patch(f'/api/v1/campaigns/{campaign_id}/status', headers=headers,
                          json={'status': 'active'})
    assert active.status_code == 200, active.text
    assert client.put(f'/api/v1/jobs/{job_id}/requirements', headers=headers,
                      json=requirements()).status_code == 409
    candidate = client.post('/api/v1/candidates', headers=headers, json={
        'full_name': 'Candidat Test', 'email': 'candidate@test.example', 'phone': '+2430000000'})
    assert candidate.status_code == 201, candidate.text
    candidate_id = candidate.json()['id']
    app = client.post('/api/v1/applications', headers=headers, json={
        'candidate_id': candidate_id, 'campaign_id': campaign_id})
    assert app.status_code == 201, app.text
    assert client.post('/api/v1/applications', headers=headers, json={
        'candidate_id': candidate_id, 'campaign_id': campaign_id}).status_code == 409
    review = client.post(f'/api/v1/applications/{app.json()["id"]}/reviews', headers=headers,
                         json={'finding': 'needs_clarification', 'note': 'Vérifier la formation mentionnée.'})
    assert review.status_code == 201, review.text
    assert review.json()['finding'] == 'needs_clarification'
    assert len(client.get('/api/v1/audit-logs', headers=headers).json()) >= 6
    assert client.get('/api/v1/candidates', headers=headers).json()['total'] == 1
    assert client.get('/api/v1/jobs', headers=headers, params={'limit': 0}).status_code == 422


def test_tenant_isolation_all_resources(client_and_orgs):
    client, ids = client_and_orgs
    headers = auth_headers(client)
    job = new_job(client, headers).json()
    candidate = client.post('/api/v1/candidates', headers=headers,
                            json={'full_name': 'Profil Alpha'}).json()
    # Log in as a distinct administrator in tenant beta.
    with next(app.dependency_overrides[get_db]()) as db:
        other_user = User(email='admin@beta.example.org', full_name='Beta Admin',
                          password_hash=hash_password('beta-good-password-123'))
        db.add(other_user)
        db.flush()
        db.add(OrganizationMember(user_id=other_user.id, organization_id=ids['beta'],
                                  role='org_admin'))
        db.commit()
    other_login = client.post('/api/v1/auth/login', json={
        'organization_slug': 'beta', 'email': 'admin@beta.example.org',
        'password': 'beta-good-password-123'})
    assert other_login.status_code == 200, other_login.text
    beta_h = {'Authorization': f'Bearer {other_login.json()["access_token"]}'}
    assert client.get('/api/v1/jobs', headers=beta_h).json()['total'] == 0
    assert client.get('/api/v1/candidates', headers=beta_h).json()['total'] == 0
    assert client.get(f'/api/v1/jobs/{job["id"]}', headers=beta_h).status_code == 404
    assert client.get(f'/api/v1/candidates/{candidate["id"]}', headers=beta_h).status_code == 404
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements', headers=beta_h,
                      json=requirements()).status_code == 404
    assert client.get('/api/v1/campaigns/not-a-campaign', headers=beta_h).status_code == 404
    assert client.post('/api/v1/campaigns', headers=beta_h, json={
        'job_id': job['id'], 'name': 'Illicite'}).status_code == 404


def test_invitation_and_roles(client_and_orgs):
    client, _ = client_and_orgs
    headers = auth_headers(client)
    i = client.post('/api/v1/invitations', headers=headers, json={
        'email': 'recruiter@alpha.example.org', 'role': 'recruiter'})
    assert i.status_code == 201, i.text
    secret = i.json()['token']
    assert len(secret) >= 32
    assert client.get('/api/v1/invitations', headers=headers).json()[0].get('token') is None
    accepted = client.post('/api/v1/invitations/accept', json={
        'token': secret, 'full_name': 'Recruteur Test', 'password': 'test-password-very-long'})
    assert accepted.status_code == 201, accepted.text
    assert client.post('/api/v1/invitations/accept', json={
        'token': secret, 'full_name': 'Recruteur Test', 'password': 'test-password-very-long'}).status_code == 400
    recruiter_login = client.post('/api/v1/auth/login', json={
        'organization_slug': 'alpha', 'email': 'recruiter@alpha.example.org',
        'password': 'test-password-very-long'})
    assert recruiter_login.status_code == 200
    h = {'Authorization': f'Bearer {recruiter_login.json()["access_token"]}'}
    assert client.get('/api/v1/members', headers=h).status_code == 403
    assert new_job(client, h).status_code == 201
    members = client.get('/api/v1/members', headers=headers).json()
    recruiter_member = next(m for m in members if m['role'] == 'recruiter')
    changed = client.patch(f'/api/v1/members/{recruiter_member["id"]}', headers=headers,
                           json={'role': 'evaluator'})
    assert changed.status_code == 200, changed.text
    assert new_job(client, h).status_code == 403
    assert client.get('/api/v1/candidates', headers=h).status_code == 403
    admin_member = next(m for m in members if m['role'] == 'org_admin')
    assert client.patch(f'/api/v1/members/{admin_member["id"]}', headers=headers,
                        json={'is_active': False}).status_code == 409
    deactivate = client.patch(f'/api/v1/members/{recruiter_member["id"]}', headers=headers,
                              json={'is_active': False})
    assert deactivate.status_code == 200
    assert client.get('/api/v1/auth/me', headers=h).status_code == 401


def test_input_validation(client_and_orgs):
    client, _ = client_and_orgs
    headers = auth_headers(client)
    invalid = client.post('/api/v1/jobs', headers=headers, json={
        'title': 'Un poste', 'description': 'Description suffisante',
        'opens_on': '2026-11-01', 'closes_on': '2026-10-01'})
    assert invalid.status_code == 422
    job = new_job(client, headers).json()
    bad = requirements()
    bad['items'].append(bad['items'][0])
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements',
                      headers=headers, json=bad).status_code == 422
    assert client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm', headers=headers,
                       json={'expected_version': 1}).status_code == 409
