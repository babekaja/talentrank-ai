from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.documents.storage import PrivateStorage, get_storage
from app.models import CVDocument, DocumentPage, ExtractionWarning, ProcessingTask
from app.services.audit import record
from app.api.v1.uploads import enqueue

router = APIRouter()


def scoped_document(doc_id: str, actor: Principal, db: Session) -> CVDocument:
    doc = db.scalar(select(CVDocument).where(CVDocument.id == doc_id,
                     CVDocument.organization_id == actor.organization.id))
    if doc is None:
        raise HTTPException(404, 'CV introuvable')
    return doc


@router.get('/documents/{doc_id}')
def detail(doc_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
           db: Session = Depends(get_db)):
    d = scoped_document(doc_id, actor, db)
    warnings = db.scalars(select(ExtractionWarning).where(ExtractionWarning.document_id == d.id)).all()
    return {'id': d.id, 'filename': d.filename, 'status': d.status, 'page_count': d.page_count,
            'error_code': d.error_code, 'application_id': d.application_id,
            'warnings': [{'page_number': w.page_number, 'code': w.code, 'message': w.message}
                         for w in warnings]}


@router.get('/documents/{doc_id}/pages')
def pages(doc_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
          db: Session = Depends(get_db)):
    d = scoped_document(doc_id, actor, db)
    rows = db.scalars(select(DocumentPage).where(DocumentPage.document_id == d.id)
                      .order_by(DocumentPage.page_number)).all()
    record(db, actor, 'document.text.viewed', 'document', doc_id)
    db.commit()
    return {'items': [{'page_number': p.page_number, 'text': p.text,
                       'method': p.extraction_method, 'version': p.version,
                       'verification_status': p.verification_status} for p in rows]}


@router.get('/documents/{doc_id}/download')
def download(doc_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
             db: Session = Depends(get_db), storage: PrivateStorage = Depends(get_storage)):
    d = scoped_document(doc_id, actor, db)
    try:
        data = storage.get(d.object_key)
    except Exception:
        raise HTTPException(503, 'Document indisponible dans le stockage') from None
    record(db, actor, 'document.original.viewed', 'document', doc_id)
    db.commit()
    def chunks():
        try:
            for block in data.stream(1024 * 1024):
                yield block
        finally:
            data.close()
            if hasattr(data, 'release_conn'): data.release_conn()
    return StreamingResponse(chunks(), media_type=d.content_type, headers={
        'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
        'Content-Disposition':f'attachment; filename="cv-{d.id}.{ "pdf" if d.content_type == "application/pdf" else "docx" }"'})


@router.post('/documents/{doc_id}/retry')
def retry(doc_id: str, actor: Principal = Depends(require_role('org_admin', 'recruiter')),
          db: Session = Depends(get_db)):
    d = scoped_document(doc_id, actor, db)
    if d.status == 'processing':
        from datetime import timedelta
        from app.models.auth import utcnow
        if d.processing_started_at and d.processing_started_at < utcnow() - timedelta(minutes=10):
            d.status = 'pending'
            db.commit()
    if d.status not in {'failed', 'pending'}:
        raise HTTPException(409, 'Document non éligible à une nouvelle tentative')
    if d.attempt_count >= 3:
        raise HTTPException(409, 'Trois tentatives effectuées, contrôle manuel requis')
    queued = enqueue(d.id, db)
    return {'id': d.id, 'queued': queued}
