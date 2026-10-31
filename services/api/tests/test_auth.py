from app.core.security import create_access_token


def authenticate(client):
    return client.post('/api/v1/auth/login', json={
        'email': 'admin@alpha.example.org', 'password': 'a-good-password-123',
        'organization_slug': 'alpha'
    })


def test_health_ready(client_and_orgs):
    client, _ = client_and_orgs
    assert client.get('/health/live').json()['status'] == 'alive'
    assert client.get('/health/ready').json()['status'] == 'ready'


def test_login_profile_and_tenant_summary(client_and_orgs):
    client, _ = client_and_orgs
    response = authenticate(client)
    assert response.status_code == 200, response.text
    token = response.json()['access_token']
    assert response.json()['expires_in'] == 900
    assert client.cookies.get('talentrank_refresh')
    headers = {'Authorization': f'Bearer {token}'}
    user = client.get('/api/v1/auth/me', headers=headers)
    assert user.status_code == 200
    assert user.json()['organization_slug'] == 'alpha'
    assert user.json()['role'] == 'org_admin'
    org = client.get('/api/v1/organizations/current', headers=headers)
    assert org.status_code == 200
    assert org.json()['active_members'] == 1
    assert org.json()['slug'] == 'alpha'


def test_remember_me_controls_cookie_persistence(client_and_orgs):
    client, _ = client_and_orgs
    session_only = authenticate(client)
    assert session_only.status_code == 200
    assert 'Max-Age' not in session_only.headers['set-cookie']

    remembered = client.post('/api/v1/auth/login', json={
        'email': 'admin@alpha.example.org', 'password': 'a-good-password-123',
        'organization_slug': 'alpha', 'remember_me': True,
    })
    assert remembered.status_code == 200
    assert f'Max-Age={30 * 86400}' in remembered.headers['set-cookie']


def test_rejects_wrong_password_and_unknown_tenant(client_and_orgs):
    client, _ = client_and_orgs
    wrong = client.post('/api/v1/auth/login', json={
        'email':'admin@alpha.example.org', 'password':'incorrect', 'organization_slug':'alpha'})
    assert wrong.status_code == 401
    other = client.post('/api/v1/auth/login', json={
        'email':'admin@alpha.example.org', 'password':'a-good-password-123', 'organization_slug':'beta'})
    assert other.status_code == 401
    assert client.get('/api/v1/auth/me').status_code in (401, 403)


def test_refresh_rotation_and_logout_revoke_access(client_and_orgs):
    client, _ = client_and_orgs
    login = authenticate(client)
    old_access = login.json()['access_token']
    old_refresh = client.cookies.get('talentrank_refresh')
    renewed = client.post('/api/v1/auth/refresh')
    assert renewed.status_code == 200
    assert renewed.json()['access_token'] != old_access
    assert client.cookies.get('talentrank_refresh') != old_refresh
    # Previous refresh token cannot be reused after rotation.
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as replay_client:
        replay_client.cookies.set('talentrank_refresh', old_refresh, path='/api/v1/auth')
        stale = replay_client.post('/api/v1/auth/refresh')
        assert stale.status_code == 401
    assert client.post('/api/v1/auth/logout').status_code == 204
    assert client.get('/api/v1/auth/me', headers={
        'Authorization': f'Bearer {old_access}'}).status_code == 401
    assert client.post('/api/v1/auth/refresh').status_code == 401


def test_org_claim_alone_is_not_enough(client_and_orgs):
    client, ids = client_and_orgs
    valid_token = authenticate(client).json()['access_token']
    me = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {valid_token}'})
    user_id = me.json()['id']
    from app.core.config import get_settings
    import jwt
    claims = jwt.decode(valid_token, get_settings().jwt_secret, algorithms=['HS256'],
                        audience=get_settings().jwt_audience, issuer=get_settings().jwt_issuer)
    counterfeit_scope = create_access_token(user_id, ids['beta'], claims['sid'])
    denied = client.get('/api/v1/organizations/current', headers={
        'Authorization': f'Bearer {counterfeit_scope}'})
    assert denied.status_code == 401


def test_cookie_origin_policy(client_and_orgs):
    client, _ = client_and_orgs
    authenticate(client)
    assert client.post('/api/v1/auth/refresh', headers={'Origin': 'https://malicious.test'}).status_code == 403
