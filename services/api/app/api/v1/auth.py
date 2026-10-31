from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    Principal, active_principal, create_access_token, digest_token,
    generate_refresh_token, get_current_principal, hash_password, verify_password, dummy_password_hash,
)
from app.models import Organization, OrganizationMember, User, UserSession
from app.models.auth import utcnow
from app.schemas.auth import DemoLoginRequest, LoginRequest, MeResponse, OrganizationSummary, RegisterRequest, TokenResponse
from app.services.audit import record

router = APIRouter()
COOKIE = 'talentrank_refresh'
REFRESH_DAYS = 7
REMEMBER_DAYS = 30
DEMO_MINUTES = 60


def set_refresh_cookie(response: Response, value: str, *, remember_me: bool,
                       max_age: int | None = None) -> None:
    response.set_cookie(COOKIE, value,
                        max_age=max_age if remember_me else None,
                        httponly=True, secure=get_settings().refresh_cookie_secure,
                        samesite='strict', path='/api/v1/auth')


def guard_cookie_origin(request: Request) -> None:
    origin = request.headers.get('origin')
    if origin and origin not in get_settings().origins:
        raise HTTPException(403, 'Origine non autorisée')


def me(principal: Principal) -> MeResponse:
    return MeResponse(id=principal.user.id, full_name=principal.user.full_name,
                      email=principal.user.email, organization_id=principal.organization.id,
                      organization_name=principal.organization.name,
                      organization_slug=principal.organization.slug, role=principal.role,
                      demo_mode=principal.is_demo,
                      demo_read_only=principal.is_demo and not get_settings().demo_allow_writes)


def demo_account(db: Session):
    settings = get_settings()
    if not settings.demo_enabled:
        return None
    return db.execute(select(User, Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(func.lower(User.email) == settings.demo_user_email.casefold(),
               Organization.slug == settings.demo_organization_slug,
               User.is_active.is_(True), Organization.is_active.is_(True),
               OrganizationMember.is_active.is_(True), OrganizationMember.role == 'org_admin')).first()


@router.get('/auth/demo/status')
def demo_status(response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    account = demo_account(db)
    if account is None:
        return {'enabled': False}
    user, organization, _ = account
    return {'enabled': True, 'account_name': user.full_name,
            'organization_name': organization.name, 'read_only': not get_settings().demo_allow_writes}


@router.post('/auth/demo', response_model=TokenResponse)
def demo_login(body: DemoLoginRequest, request: Request, response: Response,
               talentrank_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    guard_cookie_origin(request)
    response.headers['Cache-Control'] = 'no-store'
    if not get_settings().demo_enabled:
        raise HTTPException(404, 'Démonstration indisponible')
    account = demo_account(db)
    if account is None:
        raise HTTPException(503, 'Le compte de démonstration est momentanément indisponible')
    user, organization, membership = account
    # Un double clic réutilise la session démo de ce navigateur.
    session = None
    if talentrank_refresh:
        session = db.scalar(select(UserSession).where(
            UserSession.refresh_hash == digest_token(talentrank_refresh),
            UserSession.user_id == user.id, UserSession.organization_id == organization.id,
            UserSession.is_demo.is_(True), UserSession.revoked_at.is_(None),
            UserSession.expires_at > utcnow()))
    raw_refresh = talentrank_refresh if session is not None else generate_refresh_token()
    if session is None:
        session = UserSession(user_id=user.id, organization_id=organization.id,
            refresh_hash=digest_token(raw_refresh), remember_me=False, is_demo=True,
            expires_at=utcnow() + timedelta(minutes=DEMO_MINUTES))
        db.add(session)
        db.flush()
        record(db, Principal(user, organization, membership.role, session),
            'demo.session.started', 'user_session', session.id,
            {'read_only': not get_settings().demo_allow_writes, 'duration_minutes': DEMO_MINUTES})
        db.commit()
    set_refresh_cookie(response, raw_refresh, remember_me=False)
    return TokenResponse(access_token=create_access_token(user.id, organization.id, session.id))


@router.post('/auth/register', status_code=201, response_model=TokenResponse)
def register(body: RegisterRequest, request: Request, response: Response,
             db: Session = Depends(get_db)):
    guard_cookie_origin(request)
    email = str(body.email).lower()
    conflict = 'Création impossible avec cette adresse email ou ce code d’organisation. Connectez-vous si vous avez déjà un compte, ou choisissez un autre code.'
    if (db.scalar(select(User.id).where(User.email == email))
            or db.scalar(select(Organization.id).where(Organization.slug == body.organization_slug))):
        raise HTTPException(409, conflict)
    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password))
    organization = Organization(name=body.organization_name, slug=body.organization_slug)
    raw_refresh = generate_refresh_token()
    try:
        db.add_all([user, organization])
        db.flush()
        membership = OrganizationMember(user_id=user.id, organization_id=organization.id,
                                        role='org_admin')
        session = UserSession(user_id=user.id, organization_id=organization.id,
                              refresh_hash=digest_token(raw_refresh), remember_me=False,
                              expires_at=utcnow() + timedelta(days=REFRESH_DAYS))
        db.add_all([membership, session])
        db.flush()
        record(db, Principal(user, organization, membership.role, session),
               'account.created', 'organization', organization.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, conflict) from None
    except Exception:
        db.rollback()
        raise HTTPException(503, 'Création indisponible pour le moment. Réessayez plus tard.') from None
    set_refresh_cookie(response, raw_refresh, remember_me=False)
    return TokenResponse(access_token=create_access_token(user.id, organization.id, session.id))


@router.post('/auth/login', response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    # Query deliberately checks membership and organization in one query.
    record = db.execute(select(User, Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(User.email == str(body.email).lower(), Organization.slug == body.organization_slug,
               User.is_active.is_(True), Organization.is_active.is_(True),
               OrganizationMember.is_active.is_(True))).first()
    if record is None:
        verify_password(body.password, dummy_password_hash)
        raise HTTPException(401, 'Identifiants invalides')
    if not verify_password(body.password, record[0].password_hash):
        raise HTTPException(401, 'Identifiants invalides')
    user, org, _ = record
    raw_refresh = generate_refresh_token()
    refresh_days = REMEMBER_DAYS if body.remember_me else REFRESH_DAYS
    session = UserSession(user_id=user.id, organization_id=org.id,
                          refresh_hash=digest_token(raw_refresh),
                          expires_at=utcnow() + timedelta(days=refresh_days),
                          remember_me=body.remember_me)
    db.add(session)
    db.commit()
    set_refresh_cookie(response, raw_refresh, remember_me=body.remember_me,
                       max_age=refresh_days * 86400)
    return TokenResponse(access_token=create_access_token(user.id, org.id, session.id))


@router.post('/auth/refresh', response_model=TokenResponse)
def refresh(request: Request, response: Response,
            talentrank_refresh: str | None = Cookie(default=None),
            db: Session = Depends(get_db)):
    guard_cookie_origin(request)
    if not talentrank_refresh:
        raise HTTPException(401, 'Session absente')
    session = db.scalar(select(UserSession)
                        .where(UserSession.refresh_hash == digest_token(talentrank_refresh),
                               UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow())
                        .with_for_update())
    if not session:
        raise HTTPException(401, 'Session expirée')
    principal = active_principal(db, session.user_id, session.organization_id, session.id)
    if principal is None:
        raise HTTPException(401, 'Session révoquée')
    new_token = generate_refresh_token()
    session.refresh_hash = digest_token(new_token)
    db.commit()
    remaining = max(0, int((session.expires_at - utcnow()).total_seconds()))
    set_refresh_cookie(response, new_token, remember_me=session.remember_me,
                       max_age=remaining)
    return TokenResponse(access_token=create_access_token(session.user_id, session.organization_id, session.id))


@router.post('/auth/logout', status_code=204)
def logout(request: Request, response: Response,
           talentrank_refresh: str | None = Cookie(default=None),
           db: Session = Depends(get_db)):
    guard_cookie_origin(request)
    if talentrank_refresh:
        session = db.scalar(select(UserSession)
                            .where(UserSession.refresh_hash == digest_token(talentrank_refresh)))
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            db.commit()
    response.delete_cookie(COOKIE, path='/api/v1/auth',
                           secure=get_settings().refresh_cookie_secure, samesite='strict')
    return None


@router.get('/auth/me', response_model=MeResponse)
def current_user(principal: Principal = Depends(get_current_principal)):
    return me(principal)


@router.get('/organizations/current', response_model=OrganizationSummary)
def organization_current(principal: Principal = Depends(get_current_principal),
                         db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(OrganizationMember).join(User)
                      .where(OrganizationMember.organization_id == principal.organization.id,
                             OrganizationMember.is_active.is_(True), User.is_active.is_(True)))
    return OrganizationSummary(id=principal.organization.id, name=principal.organization.name,
                               slug=principal.organization.slug, active_members=count or 0)
