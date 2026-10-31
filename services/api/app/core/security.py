import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Organization, OrganizationMember, User, UserSession
from app.models.auth import utcnow

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Comparable password-verification work for unknown users/tenants.
dummy_password_hash = password_hasher.hash('dummy-not-a-login-password')
bearer = HTTPBearer(auto_error=False)


def hash_password(value: str) -> str:
    return password_hasher.hash(value)


def verify_password(value: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, value)
    except (InvalidHashError, VerifyMismatchError, VerificationError):
        return False


def digest_token(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: str, organization_id: str, session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {'sub': user_id, 'org': organization_id, 'sid': session_id,
         'iss': settings.jwt_issuer, 'aud': settings.jwt_audience,
         'iat': now, 'exp': now + timedelta(minutes=15), 'jti': secrets.token_hex(16)},
        settings.jwt_secret, algorithm='HS256',
    )


class Principal:
    def __init__(self, user: User, organization: Organization, role: str, session: UserSession):
        self.user = user
        self.organization = organization
        self.role = role
        self.session = session

    @property
    def is_demo(self) -> bool:
        return bool(getattr(self.session, 'is_demo', False))


def active_principal(db: Session, user_id: str, organization_id: str, session_id: str) -> Principal | None:
    record = db.execute(
        select(User, Organization, OrganizationMember, UserSession)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .join(UserSession, UserSession.user_id == User.id)
        .where(User.id == user_id, Organization.id == organization_id,
               UserSession.id == session_id, UserSession.organization_id == Organization.id,
               User.is_active.is_(True), Organization.is_active.is_(True),
               OrganizationMember.is_active.is_(True), UserSession.revoked_at.is_(None),
               UserSession.expires_at > utcnow())
    ).first()
    if record is None:
        return None
    user, org, membership, session = record
    if getattr(session, 'is_demo', False):
        settings = get_settings()
        if (not settings.demo_enabled or user.email.casefold() != settings.demo_user_email.casefold()
                or org.slug != settings.demo_organization_slug or membership.role != 'org_admin'):
            return None
    return Principal(user, org, membership.role, session)


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Principal:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Authentification requise', headers={'WWW-Authenticate': 'Bearer'})
    settings = get_settings()
    try:
        claims = jwt.decode(credentials.credentials, settings.jwt_secret,
                            algorithms=['HS256'], audience=settings.jwt_audience,
                            issuer=settings.jwt_issuer,
                            options={'require': ['sub', 'org', 'sid', 'iss', 'aud', 'iat', 'exp']})
        principal = active_principal(db, claims['sub'], claims['org'], claims['sid'])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        principal = None
    if principal is None:
        raise HTTPException(401, 'Session invalide ou expirée', headers={'WWW-Authenticate': 'Bearer'})
    if principal.is_demo:
        from app.core.demo import guard_demo_request
        guard_demo_request(request)
    return principal
