"""Accès public au seul compte démo configuré, avec sessions révocables."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Job, OrganizationMember, User, UserSession
from app.models.auth import utcnow
from test_auth import authenticate


@pytest.fixture
def demo_enabled(client_and_orgs,monkeypatch):
    settings=get_settings()
    monkeypatch.setattr(settings,'demo_enabled',True)
    monkeypatch.setattr(settings,'demo_user_email','admin@alpha.example.org')
    monkeypatch.setattr(settings,'demo_organization_slug','alpha')
    monkeypatch.setattr(settings,'demo_allow_writes',False)
    return client_and_orgs


def headers_for(response):
    assert response.status_code==200,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_demo_disabled_by_default(client_and_orgs):
    client,_=client_and_orgs
    assert client.get('/api/v1/auth/demo/status').json()=={'enabled':False}
    assert client.post('/api/v1/auth/demo',json={}).status_code==404
    assert client.get('/api/v1/auth/me').status_code==401


def test_demo_opens_fixed_account_without_credentials_and_keeps_password(demo_enabled):
    client,orgs=demo_enabled
    with next(app.dependency_overrides[get_db]()) as db:
        previous=db.scalar(select(User.password_hash).where(User.email=='admin@alpha.example.org'))
    status=client.get('/api/v1/auth/demo/status')
    assert status.json()['enabled'] is True and status.json()['read_only'] is True
    response=client.post('/api/v1/auth/demo',json={})
    headers=headers_for(response)
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age' not in cookie
    assert response.headers['cache-control']=='no-store'
    profile=client.get('/api/v1/auth/me',headers=headers).json()
    assert profile['organization_id']==orgs['alpha']
    assert profile['email']=='admin@alpha.example.org'
    assert profile['role']=='org_admin' and profile['demo_mode'] and profile['demo_read_only']
    assert client.get('/api/v1/dashboard/overview',headers=headers).status_code==200
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(User.password_hash).where(User.email=='admin@alpha.example.org'))==previous
        session=db.scalar(select(UserSession).where(UserSession.is_demo.is_(True)))
        assert session.organization_id==orgs['alpha'] and not session.remember_me
        assert timedelta(minutes=59)<session.expires_at-utcnow()<=timedelta(minutes=60)


@pytest.mark.parametrize('body',[{'email':'autre@example.org'},{'organization_slug':'beta'},{'role':'org_admin'},{'is_demo':False},{'remember_me':True}])
def test_visitor_cannot_choose_account_or_permissions(demo_enabled,body):
    client,_=demo_enabled
    assert client.post('/api/v1/auth/demo',json=body).status_code==422
    assert client.get('/api/v1/auth/me').status_code==401


def test_duplicate_click_reuses_session_and_refresh_keeps_restrictions(demo_enabled):
    client,_=demo_enabled
    original=client.post('/api/v1/auth/demo',json={})
    old_refresh=client.cookies.get('talentrank_refresh')
    assert client.post('/api/v1/auth/demo',json={}).status_code==200
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(func.count()).select_from(UserSession))==1
    refreshed=client.post('/api/v1/auth/refresh')
    headers=headers_for(refreshed)
    assert client.cookies.get('talentrank_refresh')!=old_refresh
    assert client.get('/api/v1/auth/me',headers=headers).json()['demo_mode'] is True
    assert client.post('/api/v1/jobs',headers=headers,json={'title':'Test démo','description':'Modification fictive'}).status_code==403
    assert client.post('/api/v1/auth/logout').status_code==204
    assert client.get('/api/v1/auth/me',headers=headers_for(original)).status_code==401


def test_read_only_session_cannot_change_data_or_escalate(demo_enabled,monkeypatch):
    client,_=demo_enabled
    headers=headers_for(client.post('/api/v1/auth/demo',json={}))
    for method,path,body in [
        ('post','/api/v1/candidates',{'full_name':'Profil fictif'}),
        ('post','/api/v1/matching/configuration',{'essential':70,'desirable':10,'experience':10,'projects_training':10}),
        ('patch','/api/v1/members/unknown',{'role':'org_admin'}),
        ('post','/api/v1/invitations',{'email':'test@example.org','role':'org_admin'}),
    ]:
        response=getattr(client,method)(path,headers=headers,json=body)
        assert response.status_code==403
        assert response.json()['detail']['code']=='DEMO_RESTRICTED'
    # Le contrôle dépend de la session en base, pas d'un indicateur fourni par le navigateur.
    with next(app.dependency_overrides[get_db]()) as db:
        session=db.scalar(select(UserSession).where(UserSession.is_demo.is_(True)))
        token=create_access_token(session.user_id,session.organization_id,session.id)
    assert client.post('/api/v1/candidates',headers={'Authorization':'Bearer '+token},json={'full_name':'Profil fictif'}).status_code==403
    # Une comparaison en lecture passe le garde démo, puis contrôle l'identifiant demandé.
    assert client.post('/api/v1/matching-runs/unknown/compare',headers=headers,json={'result_ids':['a','b']}).status_code==404


def test_write_demo_has_normal_admin_permissions_in_its_organization(demo_enabled,monkeypatch):
    client,orgs=demo_enabled
    monkeypatch.setattr(get_settings(),'demo_allow_writes',True)
    headers=headers_for(client.post('/api/v1/auth/demo',json={}))
    assert client.get('/api/v1/auth/me',headers=headers).json()['demo_read_only'] is False
    assert client.post('/api/v1/candidates',headers=headers,json={'full_name':'Profil fictif de démo'}).status_code==201
    assert client.post('/api/v1/invitations',headers=headers,json={'email':'test@example.org','role':'org_admin'}).status_code==201
    assert client.delete('/api/v1/training-courses/unknown',headers=headers).status_code==404
    assert client.patch('/api/v1/members/unknown',headers=headers,json={'role':'recruiter'}).status_code==404
    with next(app.dependency_overrides[get_db]()) as db:
        user=db.scalar(select(User).where(User.email=='admin@alpha.example.org'))
        foreign=Job(organization_id=orgs['beta'],title='Offre autre organisation',description='Poste fictif isolé',created_by=user.id)
        db.add(foreign);db.commit();foreign_id=foreign.id
    assert client.get(f'/api/v1/jobs/{foreign_id}',headers=headers).status_code==404
    assert client.patch(f'/api/v1/jobs/{foreign_id}',headers=headers,json={'title':'Modification refusée'}).status_code==404


def test_demo_scope_expiration_and_disabling(demo_enabled,monkeypatch):
    client,orgs=demo_enabled
    headers=headers_for(client.post('/api/v1/auth/demo',json={}))
    with next(app.dependency_overrides[get_db]()) as db:
        session=db.scalar(select(UserSession).where(UserSession.is_demo.is_(True)))
        foreign=create_access_token(session.user_id,orgs['beta'],session.id)
    assert client.get('/api/v1/organizations/current',headers={'Authorization':'Bearer '+foreign}).status_code==401
    monkeypatch.setattr(get_settings(),'demo_enabled',False)
    assert client.get('/api/v1/auth/me',headers=headers).status_code==401
    assert client.post('/api/v1/auth/refresh').status_code==401
    monkeypatch.setattr(get_settings(),'demo_enabled',True)
    with next(app.dependency_overrides[get_db]()) as db:
        session=db.scalar(select(UserSession).where(UserSession.is_demo.is_(True)))
        session.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    assert client.get('/api/v1/auth/me',headers=headers).status_code==401


def test_unknown_inactive_account_and_origin_fail_closed(demo_enabled,monkeypatch):
    client,_=demo_enabled
    assert client.post('/api/v1/auth/demo',json={},headers={'Origin':'https://autre.example.org'}).status_code==403
    monkeypatch.setattr(get_settings(),'demo_organization_slug','beta')
    assert client.get('/api/v1/auth/demo/status').json()=={'enabled':False}
    assert client.post('/api/v1/auth/demo',json={}).status_code==503
    monkeypatch.setattr(get_settings(),'demo_organization_slug','alpha')
    with next(app.dependency_overrides[get_db]()) as db:
        member=db.scalar(select(OrganizationMember))
        member.is_active=False;db.commit()
    assert client.post('/api/v1/auth/demo',json={}).status_code==503


def test_password_login_is_not_downgraded_to_demo(demo_enabled):
    client,_=demo_enabled
    client.post('/api/v1/auth/demo',json={})
    headers=headers_for(authenticate(client))
    profile=client.get('/api/v1/auth/me',headers=headers).json()
    assert not profile['demo_mode'] and not profile['demo_read_only']
    assert client.post('/api/v1/candidates',headers=headers,json={'full_name':'Profil fictif normal'}).status_code==201
