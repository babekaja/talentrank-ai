"""Tenant administration and single-use invitations; no delivery provider is implied."""
from datetime import timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal, digest_token, hash_password, verify_password
from app.models import Invitation, OrganizationMember, User, UserSession
from app.models.auth import utcnow
from app.schemas.recruitment import (AcceptInvitationIn, InvitationCreated,
                                     InvitationOut, InviteIn, MemberOut, MemberPatch)
from app.services.audit import record

router = APIRouter()


def member_out(member: OrganizationMember, user: User) -> MemberOut:
    return MemberOut(id=member.id, user_id=user.id, full_name=user.full_name,
                     email=user.email, role=member.role, is_active=member.is_active)


@router.get('/members', response_model=list[MemberOut])
def list_members(actor: Principal = Depends(require_role('org_admin')), db: Session = Depends(get_db)):
    rows = db.execute(select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == actor.organization.id)
        .order_by(User.full_name)).all()
    return [member_out(member, user) for member, user in rows]


@router.patch('/members/{member_id}', response_model=MemberOut)
def update_member(member_id: str, body: MemberPatch,
                  actor: Principal = Depends(require_role('org_admin')),
                  db: Session = Depends(get_db)):
    member = db.scalar(select(OrganizationMember).where(OrganizationMember.id == member_id,
        OrganizationMember.organization_id == actor.organization.id).with_for_update())
    if not member:
        raise HTTPException(404, 'Membre introuvable')
    role = body.role or member.role
    active = member.is_active if body.is_active is None else body.is_active
    if member.role == 'org_admin' and (role != 'org_admin' or not active) and member.is_active:
        admins = db.scalar(select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == actor.organization.id,
            OrganizationMember.is_active.is_(True), OrganizationMember.role == 'org_admin'))
        if admins <= 1:
            raise HTTPException(409, 'Le dernier administrateur ne peut pas être désactivé')
    member.role, member.is_active = role, active
    if not active:
        for session in db.scalars(select(UserSession).where(
            UserSession.organization_id == actor.organization.id,
            UserSession.user_id == member.user_id, UserSession.revoked_at.is_(None))):
            session.revoked_at = utcnow()
    record(db, actor, 'member.updated', 'organization_member', member.id, {'role': role, 'active': active})
    db.commit()
    return member_out(member, db.get(User, member.user_id))


@router.post('/invitations', status_code=201, response_model=InvitationCreated)
def invite(body: InviteIn, actor: Principal = Depends(require_role('org_admin')),
           db: Session = Depends(get_db)):
    email = str(body.email).lower()
    already = db.scalar(select(OrganizationMember).join(User).where(
        User.email == email, OrganizationMember.organization_id == actor.organization.id,
        OrganizationMember.is_active.is_(True)))
    if already:
        raise HTTPException(409, 'Déjà membre de cette organisation')
    secret = token_urlsafe(48)
    row = Invitation(organization_id=actor.organization.id, email=email, role=body.role,
                     token_hash=digest_token(secret), expires_at=utcnow() + timedelta(days=2),
                     created_by=actor.user.id)
    db.add(row)
    db.flush()
    record(db, actor, 'invitation.created', 'invitation', row.id, {'role': row.role})
    db.commit()
    return InvitationCreated.model_validate({**InvitationOut.model_validate(row).model_dump(), 'token': secret})


@router.get('/invitations', response_model=list[InvitationOut])
def invitations(actor: Principal = Depends(require_role('org_admin')), db: Session = Depends(get_db)):
    return db.scalars(select(Invitation).where(Invitation.organization_id == actor.organization.id)
                      .order_by(Invitation.created_at.desc()).limit(100)).all()


@router.post('/invitations/{invitation_id}/revoke', status_code=204)
def revoke_invite(invitation_id: str, actor: Principal = Depends(require_role('org_admin')),
                  db: Session = Depends(get_db)):
    row = db.scalar(select(Invitation).where(Invitation.id == invitation_id,
        Invitation.organization_id == actor.organization.id).with_for_update())
    if not row:
        raise HTTPException(404, 'Invitation introuvable')
    if row.accepted_at:
        raise HTTPException(409, 'Invitation déjà utilisée')
    row.revoked_at = utcnow()
    record(db, actor, 'invitation.revoked', 'invitation', row.id)
    db.commit()


@router.post('/invitations/accept', status_code=201)
def accept_invitation(body: AcceptInvitationIn, db: Session = Depends(get_db)):
    row = db.scalar(select(Invitation).where(Invitation.token_hash == digest_token(body.token))
                    .with_for_update())
    if not row or row.accepted_at or row.revoked_at or row.expires_at <= utcnow():
        raise HTTPException(400, 'Invitation invalide ou expirée')
    user = db.scalar(select(User).where(User.email == row.email))
    if user:
        # An invite must never let someone take over an existing account.
        if not user.is_active or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, 'Mot de passe du compte existant incorrect')
    else:
        user = User(email=row.email, full_name=body.full_name.strip(),
                    password_hash=hash_password(body.password))
        db.add(user)
        db.flush()
    member = db.scalar(select(OrganizationMember).where(
        OrganizationMember.organization_id == row.organization_id,
        OrganizationMember.user_id == user.id))
    if member and member.is_active:
        raise HTTPException(409, 'Déjà membre')
    if member:
        member.is_active = True
        member.role = row.role
    else:
        db.add(OrganizationMember(organization_id=row.organization_id, user_id=user.id,
                                  role=row.role))
    row.accepted_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Adhésion déjà enregistrée') from None
    return {'organization_id': row.organization_id, 'email': row.email, 'role': row.role}
