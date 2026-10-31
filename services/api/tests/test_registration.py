import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.main import app
from app.models import AuditLog, Organization, OrganizationMember, User, UserSession


def registration(**changes):
    return {
        'full_name': '  Camille Test  ', 'organization_name': '  Organisation de test  ',
        'organization_slug': 'nouvelle-organisation', 'email': 'camille@example.org',
        'password': 'un-mot-de-passe-de-test-123', **changes,
    }


def test_registration_creates_private_organization_and_session(client_and_orgs):
    client, ids = client_and_orgs
    response = client.post('/api/v1/auth/register', json=registration())
    assert response.status_code == 201, response.text
    assert set(response.json()) == {'access_token', 'token_type', 'expires_in'}
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age' not in cookie
    headers = {'Authorization': f'Bearer {response.json()["access_token"]}'}
    profile = client.get('/api/v1/auth/me', headers=headers).json()
    assert profile['full_name'] == 'Camille Test'
    assert profile['organization_name'] == 'Organisation de test'
    assert profile['organization_slug'] == 'nouvelle-organisation'
    assert profile['role'] == 'org_admin'
    assert profile['organization_id'] not in ids.values()
    assert client.get('/api/v1/organizations/current', headers=headers).json()['active_members'] == 1
    members = client.get('/api/v1/members', headers=headers).json()
    assert len(members) == 1 and members[0]['email'] == 'camille@example.org'
    with next(app.dependency_overrides[get_db]()) as db:
        user = db.get(User, profile['id'])
        assert user.password_hash.startswith('$argon2')
        assert verify_password(registration()['password'], user.password_hash)
        assert db.scalar(select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.user_id == user.id)) == 1
        assert db.scalar(select(AuditLog).where(AuditLog.organization_id == profile['organization_id'])).action == 'account.created'
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        wrong_scope = create_access_token(user.id, ids['alpha'], session.id)
    assert client.get('/api/v1/members', headers={'Authorization': f'Bearer {wrong_scope}'}).status_code == 401
    assert client.post('/api/v1/auth/refresh').status_code == 200
    assert client.post('/api/v1/auth/logout').status_code == 204
    login = client.post('/api/v1/auth/login', json={
        'email': 'CAMILLE@example.org', 'password': registration()['password'],
        'organization_slug': 'nouvelle-organisation',
    })
    assert login.status_code == 200


@pytest.mark.parametrize('changes', [
    {'organization_slug': 'alpha'},
    {'email': 'ADMIN@alpha.example.org'},
])
def test_registration_does_not_join_existing_organization_or_replace_user(client_and_orgs, changes):
    client, _ = client_and_orgs
    response = client.post('/api/v1/auth/register', json=registration(**changes))
    assert response.status_code == 409
    assert not client.cookies.get('talentrank_refresh')
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(func.count()).select_from(Organization)) == 2
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(OrganizationMember)) == 1


@pytest.mark.parametrize('changes', [
    {'full_name': '  '}, {'organization_name': ' '}, {'email': 'invalide'},
    {'organization_slug': 'organisation/interdite'}, {'organization_slug': 'a' * 81},
    {'password': 'trop-court'}, {'password': 'x' * 257},
    {'role': 'org_admin'}, {'organization_id': 'existing-organization'},
])
def test_registration_validates_inputs_without_echoing_password(client_and_orgs, changes):
    client, _ = client_and_orgs
    payload = registration(**changes)
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 422, response.text
    assert payload['password'] not in response.text
    assert all(set(item) == {'loc', 'msg', 'type'} for item in response.json()['detail'])
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(func.count()).select_from(Organization)) == 2
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_registration_duplicate_and_email_normalization(client_and_orgs):
    client, _ = client_and_orgs
    assert client.post('/api/v1/auth/register', json=registration(email='Camille@Example.org')).status_code == 201
    second = client.post('/api/v1/auth/register', json=registration(organization_slug='autre-organisation'))
    assert second.status_code == 409
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(User).where(User.email == 'camille@example.org')) is not None
        assert db.scalar(select(Organization).where(Organization.slug == 'autre-organisation')) is None


def test_registration_rejects_foreign_origin(client_and_orgs):
    client, _ = client_and_orgs
    response = client.post('/api/v1/auth/register', json=registration(), headers={'Origin': 'https://malicious.test'})
    assert response.status_code == 403


@pytest.mark.parametrize('endpoint', ['verify-email', 'resend-verification'])
def test_admin_signup_has_no_email_code_endpoint(client_and_orgs, endpoint):
    client, _ = client_and_orgs
    assert client.post(f'/api/v1/auth/{endpoint}', json={}).status_code == 404


def test_registration_rolls_back_all_records_on_conflict(client_and_orgs, monkeypatch):
    from sqlalchemy.orm import Session

    client, _ = client_and_orgs

    def conflict(session):
        raise IntegrityError('conflit simulé', None, Exception('doublon'))

    monkeypatch.setattr(Session, 'commit', conflict)
    response = client.post('/api/v1/auth/register', json=registration())
    assert response.status_code == 409
    assert 'set-cookie' not in response.headers
    with next(app.dependency_overrides[get_db]()) as db:
        for model, expected in ((Organization, 2), (User, 1), (OrganizationMember, 1), (UserSession, 0), (AuditLog, 0)):
            assert db.scalar(select(func.count()).select_from(model)) == expected
