"""Phase 3 uploads: no public object links, tenant scoping and bounded request processing."""
import os
import zipfile
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.documents.storage import PrivateStorage, get_storage
from app.documents.malware import scan_file
from app.documents.validation import clean_name, inspect_cv, spool_upload, spool_zip_entry, validate_zip
from app.models import Application, CVDocument, Candidate, ProcessingTask, RecruitmentCampaign, UploadBatch
from app.models.auth import uid
from app.services.audit import record

router = APIRouter()

class BatchIn(BaseModel):
    campaign_id: str


def batch_row(batch_id: str, actor: Principal, db: Session) -> UploadBatch:
    row = db.scalar(select(UploadBatch).where(UploadBatch.id == batch_id,
                 UploadBatch.organization_id == actor.organization.id))
    if not row:
        raise HTTPException(404, 'Lot introuvable')
    return row


def campaign_for_upload(campaign_id: str, actor: Principal, db: Session):
    row = db.scalar(select(RecruitmentCampaign).where(
        RecruitmentCampaign.id == campaign_id,
        RecruitmentCampaign.organization_id == actor.organization.id))
    if not row:
        raise HTTPException(404, 'Campagne introuvable')
    if row.status != 'active':
        raise HTTPException(409, 'La campagne doit être active pour importer des CV')
    return row


@router.post('/uploads/batches', status_code=201)
def create_batch(body: BatchIn, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                 db: Session = Depends(get_db)):
    campaign_for_upload(body.campaign_id, actor, db)
    row = UploadBatch(organization_id=actor.organization.id,
                      campaign_id=body.campaign_id, created_by=actor.user.id)
    db.add(row)
    db.flush()
    record(db, actor, 'upload.batch.created', 'upload_batch', row.id)
    db.commit()
    return {'id': row.id, 'campaign_id': row.campaign_id, 'created_at': row.created_at}


def enqueue(document_id: str, db: Session) -> bool:
    """Successful enqueue means Redis accepted the message, NOT that extraction succeeded."""
    task = db.scalar(select(ProcessingTask).where(ProcessingTask.document_id == document_id)
                     .order_by(ProcessingTask.created_at.desc()).limit(1))
    try:
        from app.workers.tasks import extract_task
        result = extract_task.delay(document_id)
        if task: task.celery_task_id = result.id; task.status = 'queued'; task.error_code = None
        db.commit()
        return True
    except Exception:
        db.rollback()
        task = db.scalar(select(ProcessingTask).where(ProcessingTask.document_id == document_id)
                         .order_by(ProcessingTask.created_at.desc()).limit(1))
        if task: task.status = 'queue_failed'; task.error_code = 'QUEUE_UNAVAILABLE'
        db.commit()
        return False


def ingest(path: str, name: str, length: int, sha: str, batch: UploadBatch, actor: Principal,
           db: Session, storage: PrivateStorage):
    mime = inspect_cv(path, name)
    scan_file(path)
    existing = db.scalar(select(CVDocument).where(
        CVDocument.organization_id == actor.organization.id,
        CVDocument.campaign_id == batch.campaign_id, CVDocument.sha256 == sha))
    if existing:
        return {'id': existing.id, 'filename': name, 'status': 'duplicate', 'queued': False}
    # Serialize capacity checks across simultaneous API uploads for the same batch.
    # Under MySQL/InnoDB, SELECT ... FOR UPDATE holds this parent-row lock
    # until ingest commits. A preliminary count outside the lock is not safe.
    locked_batch = db.scalar(select(UploadBatch.id).where(
        UploadBatch.id == batch.id,
        UploadBatch.organization_id == actor.organization.id).with_for_update())
    if locked_batch is None:
        raise HTTPException(404, 'Lot introuvable')
    n = db.scalar(select(func.count()).select_from(CVDocument).where(CVDocument.batch_id == batch.id)) or 0
    if n >= get_settings().max_batch_documents:
        raise HTTPException(413, 'Nombre maximal de CV atteint pour ce lot')
    candidate = Candidate(organization_id=actor.organization.id,
                          reference=f'TR-{uid()[:8].upper()}', full_name='Non renseigné')
    db.add(candidate)
    db.flush()
    application = Application(organization_id=actor.organization.id,
                              campaign_id=batch.campaign_id, candidate_id=candidate.id)
    db.add(application)
    db.flush()
    # The raw filename is never used as an object path, preventing collisions/path traversal.
    document_id = uid()
    key = f'{actor.organization.id}/{batch.id}/{document_id}'
    doc = CVDocument(id=document_id, organization_id=actor.organization.id,
                     campaign_id=batch.campaign_id, batch_id=batch.id, application_id=application.id,
                     filename=name, sha256=sha, byte_size=length, content_type=mime,
                     object_key=key, status='pending')
    db.add(doc)
    db.add(ProcessingTask(document_id=document_id, status='pending'))
    try:
        storage.put(key, path, length, mime)
        db.flush()
        record(db, actor, 'document.uploaded', 'document', document_id, {'batch_id': batch.id})
        db.commit()
    except IntegrityError:
        db.rollback()
        try: storage.delete(key)
        except Exception: pass
        existing = db.scalar(select(CVDocument).where(
            CVDocument.organization_id == actor.organization.id,
            CVDocument.campaign_id == batch.campaign_id, CVDocument.sha256 == sha))
        if existing:
            return {'id': existing.id, 'filename': name, 'status': 'duplicate', 'queued': False}
        raise HTTPException(409, 'Import concurrent en conflit') from None
    except Exception:
        db.rollback()
        try: storage.delete(key)
        except Exception: pass
        raise HTTPException(503, 'Stockage indisponible') from None
    queued = enqueue(document_id, db)
    return {'id': document_id, 'filename': name, 'status': 'pending', 'queued': queued}


@router.post('/uploads/batches/{batch_id}/files', status_code=201)
async def upload_cv(batch_id: str, file: Annotated[UploadFile, File()], response: Response,
                    actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                    db: Session = Depends(get_db), storage: PrivateStorage = Depends(get_storage)):
    batch = batch_row(batch_id, actor, db)
    campaign_for_upload(batch.campaign_id, actor, db)
    name = clean_name(file.filename or '')
    setting = get_settings()
    is_zip = name.lower().endswith('.zip')
    path, length, sha = await spool_upload(file, setting.max_zip_bytes if is_zip else setting.max_cv_bytes)
    try:
        try:
            storage.ensure_bucket()
        except Exception:
            raise HTTPException(503, 'Stockage privé indisponible') from None
        if not is_zip:
            return {'items': [ingest(path, name, length, sha, batch, actor, db, storage)]}
        with open(path, 'rb') as header:
            if header.read(2) != b'PK':
                raise HTTPException(415, 'Signature ZIP invalide')
        count = db.scalar(select(func.count()).select_from(CVDocument).where(CVDocument.batch_id == batch.id)) or 0
        remaining = setting.max_batch_documents - count
        if remaining < 1:
            raise HTTPException(413, 'Lot complet')
        unsupported = []
        entries = validate_zip(path, remaining, setting.max_cv_bytes,
                               min(setting.max_batch_documents * setting.max_cv_bytes,
                                   1000 * 1024 * 1024), unsupported=unsupported)
        items = []
        failures = [{'filename': name, 'code': 415,
                     'message': 'Format non autorisé : seuls les PDF et DOCX sont importés'}
                    for name in unsupported]
        with zipfile.ZipFile(path) as archive:
            for info in entries:
                filename = clean_name(info.filename)
                member_path = None
                try:
                    member_path, size, document_digest = spool_zip_entry(
                        archive, info, setting.max_cv_bytes)
                    items.append(ingest(member_path, filename, size,
                                        document_digest, batch, actor, db, storage))
                except HTTPException as exc:
                    # Previous documents have already been committed; report the
                    # partial result instead of pretending the whole ZIP failed.
                    failures.append({'filename': filename, 'code': exc.status_code,
                                     'message': str(exc.detail)[:180]})
                    if exc.status_code >= 500:
                        break  # A failed backend should not be hammered for 3000 entries.
                except (ValueError, OSError, zipfile.BadZipFile):
                    failures.append({'filename': filename, 'code': 422,
                                     'message': 'Fichier impossible à importer'})
                finally:
                    if member_path is not None and os.path.exists(member_path):
                        os.unlink(member_path)
        if failures:
            response.status_code = 207  # Multi-status: clients must inspect failures.
        return {'items': items, 'failures': failures,
                'accepted': sum(item.get('status') != 'duplicate' for item in items),
                'rejected': len(failures),
                'message': 'Import partiel : examiner les fichiers refusés' if failures else 'Import terminé'}
    finally:
        os.unlink(path)


@router.get('/uploads/batches')
def list_batches(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                 actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                 db: Session = Depends(get_db)):
    cond = UploadBatch.organization_id == actor.organization.id
    total = db.scalar(select(func.count()).select_from(UploadBatch).where(cond)) or 0
    batches = db.scalars(select(UploadBatch).where(cond)
                         .order_by(UploadBatch.created_at.desc(), UploadBatch.id.desc())
                         .limit(limit).offset(offset)).all()
    return {'items': [dict(id=b.id, campaign_id=b.campaign_id, created_at=b.created_at) for b in batches],
            'total': total, 'limit': limit, 'offset': offset}


@router.get('/uploads/batches/{batch_id}')
def batch_detail(batch_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                 db: Session = Depends(get_db)):
    row = batch_row(batch_id, actor, db)
    return {'id': row.id, 'campaign_id': row.campaign_id, 'created_at': row.created_at}


@router.get('/uploads/batches/{batch_id}/progress')
def batch_progress(batch_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                   db: Session = Depends(get_db)):
    batch_row(batch_id, actor, db)
    counts = dict(db.execute(select(CVDocument.status, func.count()).where(
        CVDocument.batch_id == batch_id,
        CVDocument.organization_id == actor.organization.id).group_by(CVDocument.status)).all())
    total = sum(counts.values())
    return {'total': total, 'processed': counts.get('completed', 0) + counts.get('needs_review', 0),
            'completed': counts.get('completed', 0), 'needs_review': counts.get('needs_review', 0),
            'failed': counts.get('failed', 0), 'processing': counts.get('processing', 0),
            'pending': counts.get('pending', 0)}


@router.get('/uploads/batches/{batch_id}/documents')
def batch_documents(batch_id: str, limit: int = Query(25, ge=1, le=100),
                    offset: int = Query(0, ge=0),
                    actor: Principal = Depends(require_role('org_admin', 'recruiter')),
                    db: Session = Depends(get_db)):
    batch_row(batch_id, actor, db)
    cond = (CVDocument.organization_id == actor.organization.id, CVDocument.batch_id == batch_id)
    total = db.scalar(select(func.count()).select_from(CVDocument).where(*cond)) or 0
    rows = db.scalars(select(CVDocument).where(*cond).order_by(CVDocument.created_at.desc())
                      .limit(limit).offset(offset)).all()
    return {'items': [{'id': r.id, 'filename': r.filename, 'status': r.status,
                       'error_code': r.error_code, 'page_count': r.page_count,
                       'application_id': r.application_id} for r in rows],
            'total': total, 'offset': offset, 'limit': limit}


@router.get('/uploads/batches/{batch_id}/pipeline-progress')
def batch_pipeline_progress(batch_id: str,
         actor: Principal = Depends(require_role('org_admin', 'recruiter')),
         db: Session = Depends(get_db)):
    """Real DB counts for extraction + NLP; no simulated progress."""
    from app.models import DocumentNlpRun
    batch_row(batch_id,actor,db)
    documents=db.scalar(select(func.count()).select_from(CVDocument).where(
        CVDocument.batch_id==batch_id,CVDocument.organization_id==actor.organization.id)) or 0
    nlp=dict(db.execute(select(DocumentNlpRun.status,func.count())
        .join(CVDocument,CVDocument.id==DocumentNlpRun.document_id)
        .where(CVDocument.batch_id==batch_id,CVDocument.organization_id==actor.organization.id,
               DocumentNlpRun.organization_id==actor.organization.id)
        .group_by(DocumentNlpRun.status)).all())
    return {'total_documents':documents,'nlp_completed':nlp.get('completed',0),
            'nlp_failed':nlp.get('failed',0),'nlp_processing':nlp.get('processing',0),
            'nlp_pending':nlp.get('pending',0),
            'nlp_not_started':max(0,documents-sum(nlp.values())),
            'stage':'real_database_counts'}
