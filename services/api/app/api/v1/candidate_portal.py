"""Candidate-owned training consent, verified by an email-delivered single-use secret.

The portal NEVER returns hiring scores, other applicants' data, or raw CV files.
No link contains an access secret: candidate enters the email code through POST.
"""
from datetime import timedelta
from email.message import EmailMessage
import hashlib
import secrets
import smtplib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import (Candidate, CandidateContact, CandidateConsentEvent,
    CandidatePortalToken, CandidatePortalSession, Organization, MatchingResult, MatchingRun,
    MatchingCriterionResult, TrainingCourse)
from app.models.auth import utcnow
from app.services.audit import record

router = APIRouter(prefix='/candidate-portal')
NOTICE_VERSION = 'training-suggestions-fr-v1'
PURPOSE = 'training_suggestions'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def deliver_candidate_code(to_email: str, code: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg['Subject'] = 'TalentRank : code de vérification de votre espace candidat'
    msg['From'] = settings.candidate_portal_from_email
    msg['To'] = to_email
    msg.set_content('Votre code de connexion temporaire : ' + code + '\n'
                    'Valable 15 minutes, une seule utilisation. Ne le transmettez à personne.\n'
                    'Accès : ' + settings.candidate_portal_base_url.rstrip('/') + '/espace-candidat')
    with smtplib.SMTP(settings.candidate_portal_smtp_host,
                      settings.candidate_portal_smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.candidate_portal_smtp_user:
            smtp.login(settings.candidate_portal_smtp_user,
                       settings.candidate_portal_smtp_password)
        smtp.send_message(msg)


def require_portal_enabled():
    settings = get_settings()
    if not settings.candidate_portal_enabled or not settings.candidate_portal_smtp_host or not settings.candidate_portal_from_email:
        raise HTTPException(503, 'Espace candidat indisponible : messagerie sécurisée non configurée')


class VerifyIn(BaseModel):
    code: str = Field(min_length=40, max_length=160)


class ConsentUpdate(BaseModel):
    consent: bool
    notice_version: str = Field(pattern='^training-suggestions-fr-v1$')


@router.post('/candidates/{candidate_id}/send-access-code', status_code=202)
def send_access_code(candidate_id: str,
        actor: Principal = Depends(require_role('org_admin', 'recruiter')),
        db: Session = Depends(get_db)):
    require_portal_enabled()
    row = db.execute(select(Candidate, CandidateContact)
        .join(CandidateContact, CandidateContact.candidate_id == Candidate.id)
        .where(Candidate.id == candidate_id, Candidate.organization_id == actor.organization.id)).first()
    if row is None or not row[1].email:
        raise HTTPException(422, 'Adresse email du candidat absente')
    candidate, contact = row
    now = utcnow()
    previous = db.scalars(select(CandidatePortalToken).where(
        CandidatePortalToken.candidate_id == candidate_id,
        CandidatePortalToken.organization_id == actor.organization.id,
        CandidatePortalToken.used_at.is_(None),
        CandidatePortalToken.revoked_at.is_(None))).all()
    # Anti-spam throttle per candidate (DB-based; no local memory assumption).
    if any((now - token.created_at).total_seconds() < 120 for token in previous):
        raise HTTPException(429, 'Un code a été envoyé récemment. Réessayez plus tard.')
    for token in previous:
        token.revoked_at = now
    code = secrets.token_urlsafe(36)
    row = CandidatePortalToken(candidate_id=candidate.id, organization_id=actor.organization.id,
        email_fingerprint=digest(contact.email.strip().lower()), challenge_hash=digest(code),
        expires_at=now + timedelta(minutes=15))
    db.add(row)
    try:
        # Never return the code to the recruiter; delivery failure rolls back token.
        deliver_candidate_code(contact.email, code)
        db.flush()
        record(db, actor, 'portal.access_code.sent', 'candidate', candidate.id)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(503, 'Échec de remise du code sécurisé') from None
    return {'sent': True, 'expires_in_minutes': 15,
            'message': 'Code envoyé au contact enregistré. Aucun consentement enregistré automatiquement.'}


@router.post('/verify')
def verify(body: VerifyIn, db: Session = Depends(get_db)):
    require_portal_enabled()
    now = utcnow()
    challenge = db.scalar(select(CandidatePortalToken).where(
        CandidatePortalToken.challenge_hash == digest(body.code)).with_for_update())
    if not challenge or challenge.revoked_at or challenge.used_at or challenge.expires_at <= now:
        raise HTTPException(401, 'Code invalide ou expiré')
    # A previously issued code must not survive deactivation of its organisation.
    membership = db.scalar(select(Candidate.id).join(Organization, Organization.id == Candidate.organization_id)
        .where(Candidate.id == challenge.candidate_id,
               Candidate.organization_id == challenge.organization_id,
               Organization.is_active.is_(True)))
    if membership is None:
        raise HTTPException(401, 'Code invalide ou expiré')
    contact = db.get(CandidateContact, challenge.candidate_id)
    if not contact or not contact.email or digest(contact.email.strip().lower()) != challenge.email_fingerprint:
        raise HTTPException(401, 'Code invalide ou expiré')
    secret = secrets.token_urlsafe(40)
    db.add(CandidatePortalSession(candidate_id=challenge.candidate_id,
        organization_id=challenge.organization_id, access_hash=digest(secret),
        expires_at=now + timedelta(minutes=30)))
    challenge.used_at = now
    db.commit()
    return {'access_token': secret, 'token_type': 'bearer', 'expires_in': 1800,
            'notice_version': NOTICE_VERSION}


def portal_session(authorization: Annotated[str | None, Header()] = None,
                   db: Session = Depends(get_db)) -> CandidatePortalSession:
    require_portal_enabled()
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authentification candidat nécessaire')
    secret = authorization[7:]
    if not 40 <= len(secret) <= 160:
        raise HTTPException(401, 'Session invalide')
    session = db.scalar(select(CandidatePortalSession).where(
        CandidatePortalSession.access_hash == digest(secret)))
    if session is None or session.revoked_at or session.expires_at <= utcnow():
        raise HTTPException(401, 'Session expirée ou révoquée')
    # Verify tenant lifecycle on *every* portal call, not only on code redemption.
    active_candidate = db.scalar(select(Candidate.id).join(Organization, Organization.id == Candidate.organization_id)
        .where(Candidate.id == session.candidate_id,
               Candidate.organization_id == session.organization_id,
               Organization.is_active.is_(True)))
    if active_candidate is None:
        raise HTTPException(401, 'Espace candidat indisponible')
    return session


def current_consent(db: Session, candidate_id: str, organization_id: str) -> bool:
    event = db.scalar(select(CandidateConsentEvent).where(
        CandidateConsentEvent.candidate_id == candidate_id,
        CandidateConsentEvent.organization_id == organization_id,
        CandidateConsentEvent.purpose == PURPOSE).order_by(
            CandidateConsentEvent.created_at.desc(), CandidateConsentEvent.id.desc()).limit(1))
    return bool(event and event.action == 'granted')


@router.get('/me')
def portal_me(session: CandidatePortalSession = Depends(portal_session),
              db: Session = Depends(get_db)):
    candidate = db.get(Candidate, session.candidate_id)
    if not candidate or candidate.organization_id != session.organization_id:
        raise HTTPException(401, 'Compte inaccessible')
    return {'candidate_reference': candidate.reference, 'training_consent': current_consent(
        db, session.candidate_id, session.organization_id), 'notice_version': NOTICE_VERSION,
        'notice': 'Facultatif : recevoir des pistes de formation à partir de critères non retrouvés dans vos CV.\n'
                  'Aucune recommandation ne prouve une lacune, ne modifie le recrutement ou ne déclenche un email.\n'
                  'Vous pouvez retirer cet accord à tout moment.'}


@router.put('/consent')
def portal_consent(body: ConsentUpdate, session: CandidatePortalSession = Depends(portal_session),
                   db: Session = Depends(get_db)):
    db.add(CandidateConsentEvent(candidate_id=session.candidate_id,
        organization_id=session.organization_id, purpose=PURPOSE,
        action='granted' if body.consent else 'withdrawn', notice_version=body.notice_version))
    db.commit()
    return {'training_consent': body.consent, 'notice_version': NOTICE_VERSION}


@router.get('/training-suggestions')
def training_suggestions(session: CandidatePortalSession = Depends(portal_session),
                         db: Session = Depends(get_db)):
    if not current_consent(db, session.candidate_id, session.organization_id):
        return {'status': 'consent_required', 'items': []}
    from app.models import Application
    matches = db.execute(select(MatchingResult, MatchingRun)
        .join(MatchingRun, MatchingRun.id == MatchingResult.run_id)
        .join(Application, Application.candidate_id == MatchingResult.candidate_id)
        .where(MatchingResult.candidate_id == session.candidate_id,
               MatchingRun.organization_id == session.organization_id,
               Application.organization_id == session.organization_id,
               Application.campaign_id == MatchingRun.campaign_id)
        .order_by(MatchingRun.created_at.desc()).limit(10)).all()
    skill_ids = set()
    for result, run in matches:
        for criterion in db.scalars(select(MatchingCriterionResult).where(
            MatchingCriterionResult.result_id == result.id,
            MatchingCriterionResult.state.in_(['not_documented', 'needs_review', 'manual_review_required']))):
            skill_id = run.skill_mapping_snapshot.get(criterion.requirement_id)
            if skill_id:
                skill_ids.add(str(skill_id))
    if not skill_ids:
        return {'status': 'no_verified_suggestions', 'items': []}
    courses = db.scalars(select(TrainingCourse).where(
        TrainingCourse.organization_id == session.organization_id,
        TrainingCourse.skill_id.in_(skill_ids),
        TrainingCourse.is_active.is_(True),
        TrainingCourse.verified_at.is_not(None)).limit(30)).all()
    return {'status': 'optional_verified_training',
            'items': [{'title':c.title,'provider':c.provider,'official_url':c.official_url,
                       'language':c.language,'level':c.level} for c in courses],
            'notice':'Formations facultatives : absence dans le CV ne signifie pas absence de compétence.'}


@router.post('/logout')
def portal_logout(session: CandidatePortalSession = Depends(portal_session),
                  db: Session = Depends(get_db)):
    session.revoked_at = utcnow()
    db.commit()
    return {'logged_out': True}
