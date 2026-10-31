"""Organization-curated real training links. No fabricated courses or verification."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.models import Skill, TrainingCourse
from app.models.auth import utcnow
from app.services.audit import record

router = APIRouter(prefix='/training-courses')


class CourseIn(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    provider: str = Field(min_length=2, max_length=180)
    official_url: HttpUrl
    language: str = Field(min_length=2, max_length=15, pattern=r'^[a-z]{2}(-[A-Za-z]{2})?$')
    level: str = Field(min_length=2, max_length=30)
    skill_id: str | None = Field(default=None, max_length=36)
    description: str = Field(default='', max_length=3000)


class CourseVerifyIn(BaseModel):
    source_checked: bool


def _row(db: Session, org_id: str, course_id: str) -> TrainingCourse:
    row = db.scalar(select(TrainingCourse).where(
        TrainingCourse.id == course_id, TrainingCourse.organization_id == org_id))
    if not row:
        raise HTTPException(404, 'Formation introuvable')
    return row


def _skill(db: Session, skill_id: str | None):
    if skill_id and not db.scalar(select(Skill.id).where(Skill.id == skill_id, Skill.active.is_(True))):
        raise HTTPException(422, 'Compétence inconnue ou désactivée')


def _out(row: TrainingCourse):
    return {'id': row.id, 'title': row.title, 'provider': row.provider,
            'official_url': row.official_url, 'language': row.language,
            'level': row.level, 'skill_id': row.skill_id,
            'description': row.description, 'is_active': row.is_active,
            'verified_at': row.verified_at, 'created_at': row.created_at}


@router.get('')
def list_courses(q: str = Query('', max_length=120),
                 skill_id: str | None = Query(None, max_length=36),
                 limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                 actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                 db: Session = Depends(get_db)):
    clauses = [TrainingCourse.organization_id == actor.organization.id,
               TrainingCourse.is_active.is_(True)]
    if skill_id:
        clauses.append(TrainingCourse.skill_id == skill_id)
    if q.strip():
        like = '%' + q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        clauses.append(TrainingCourse.title.ilike(like, escape='\\'))
    total = db.scalar(select(func.count()).select_from(TrainingCourse).where(*clauses)) or 0
    rows = db.scalars(select(TrainingCourse).where(*clauses)
                      .order_by(TrainingCourse.created_at.desc(), TrainingCourse.id.desc())
                      .offset(offset).limit(limit)).all()
    return {'items': [_out(x) for x in rows], 'total': total, 'limit': limit, 'offset': offset}


@router.post('', status_code=201)
def create_course(body: CourseIn,
                  actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                  db: Session = Depends(get_db)):
    _skill(db, body.skill_id)
    row = TrainingCourse(organization_id=actor.organization.id,
                         title=body.title.strip(), provider=body.provider.strip(),
                         official_url=str(body.official_url), language=body.language,
                         level=body.level, skill_id=body.skill_id,
                         description=body.description, is_active=True)
    db.add(row)
    db.flush()
    record(db, actor, 'training.created', 'training_course', row.id)
    db.commit()
    return _out(row)


@router.put('/{course_id}')
def update_course(course_id: str, body: CourseIn,
                  actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                  db: Session = Depends(get_db)):
    row = _row(db, actor.organization.id, course_id)
    if not row.is_active:
        raise HTTPException(409, 'Formation archivée')
    _skill(db, body.skill_id)
    row.title, row.provider, row.official_url = body.title.strip(), body.provider.strip(), str(body.official_url)
    row.language, row.level, row.skill_id = body.language, body.level, body.skill_id
    row.description, row.verified_at, row.verified_by = body.description, None, None
    row.updated_at = utcnow()
    record(db, actor, 'training.updated', 'training_course', row.id)
    db.commit()
    return _out(row)


@router.post('/{course_id}/verify')
def verify_course(course_id: str, body: CourseVerifyIn,
                  actor: Principal = Depends(require_role('org_admin')),
                  db: Session = Depends(get_db)):
    if not body.source_checked:
        raise HTTPException(422, 'Une vérification humaine explicite est obligatoire')
    row = _row(db, actor.organization.id, course_id)
    if not row.is_active:
        raise HTTPException(409, 'Formation archivée')
    row.verified_at, row.verified_by = utcnow(), actor.user.id
    record(db, actor, 'training.source_verified_by_human', 'training_course', row.id)
    db.commit()
    return _out(row)


@router.delete('/{course_id}')
def archive_course(course_id: str,
                   actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                   db: Session = Depends(get_db)):
    row = _row(db, actor.organization.id, course_id)
    row.is_active, row.verified_at, row.verified_by = False, None, None
    record(db, actor, 'training.archived', 'training_course', row.id)
    db.commit()
    return {'archived': True}
