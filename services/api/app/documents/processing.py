"""Idempotent document extraction; use only DB IDs in queue payloads, never CV text."""
import os
import shutil
import tempfile
from datetime import timedelta
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.documents.parsing import extract_document, PARSER_VERSION
from app.documents.storage import get_storage
from app.models import CVDocument, DocumentPage, ExtractionWarning, ProcessingTask
from app.models.auth import utcnow


def process_document(document_id: str, db: Session, storage=None) -> str:
    storage = storage or get_storage()
    # A row lock prevents concurrent processing in MySQL; `completed` is immutable until retry.
    doc = db.scalar(select(CVDocument).where(CVDocument.id == document_id).with_for_update())
    if doc is None:
        return 'missing'
    if doc.status in ('completed', 'needs_review'):
        return doc.status
    if doc.status == 'processing':
        if not doc.processing_started_at or doc.processing_started_at > utcnow() - timedelta(minutes=10):
            return 'already_processing'
        # Recover a timed-out/killed worker after its processing lease expires.
        doc.status = 'pending'
    if doc.status not in ('pending', 'failed'):
        return doc.status
    doc.status = 'processing'
    doc.processing_started_at = utcnow()
    doc.error_code = None
    doc.attempt_count += 1
    task = db.scalar(select(ProcessingTask).where(ProcessingTask.document_id == document_id)
                     .order_by(ProcessingTask.created_at.desc()).limit(1))
    if task:
        task.status = 'processing'
        task.attempts += 1
    db.commit()

    path = None
    try:
        fd, path = tempfile.mkstemp(prefix='tr-process-')
        with os.fdopen(fd, 'wb') as out:
            response = storage.get(doc.object_key)
            try:
                # Do not trust object-store size alone; bound downloaded body.
                remaining = doc.byte_size + 1
                for chunk in response.stream(1024 * 1024):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise ValueError('STORED_SIZE_MISMATCH')
                    out.write(chunk)
            finally:
                response.close()
                if hasattr(response, 'release_conn'):
                    response.release_conn()
        if os.path.getsize(path) != doc.byte_size:
            raise ValueError('STORED_SIZE_MISMATCH')
        import hashlib
        with open(path, 'rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != doc.sha256:
                raise ValueError('STORED_CHECKSUM_MISMATCH')
        results = extract_document(path, doc.content_type)
        # Commit complete extraction transactionally; never expose partial result pages.
        db.execute(delete(ExtractionWarning).where(ExtractionWarning.document_id == doc.id))
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        for page in results:
            db.add(DocumentPage(document_id=doc.id, page_number=page.number,
                                text=page.text, extraction_method=page.method,
                                version=PARSER_VERSION))
            for code in page.warnings:
                db.add(ExtractionWarning(document_id=doc.id, page_number=page.number,
                                         code=code, message={'NO_TEXT':'Aucun texte lisible',
                                         'OCR_EMPTY':'OCR sans texte exploitable',
                                         'OCR_UNAVAILABLE':'OCR indisponible ou erreur de lecture'}.get(code, code)))
        doc.page_count = len(results)
        doc.status = 'needs_review' if any(p.warnings for p in results) else 'completed'
        doc.processed_at = utcnow()
        doc.processing_started_at = None
        if task: task.status = doc.status
        db.commit()
        return doc.status
    except Exception as exc:
        # Do not store raw exceptions; may accidentally contain document content.
        db.rollback()
        doc = db.get(CVDocument, document_id)
        if doc:
            doc.status = 'failed'
            doc.processing_started_at = None
            doc.error_code = str(exc) if isinstance(exc, ValueError) and str(exc) in {
                'PDF_PAGE_LIMIT','DOCX_PARAGRAPH_LIMIT','UNSUPPORTED_FORMAT',
                'STORED_SIZE_MISMATCH','STORED_CHECKSUM_MISMATCH'} else 'EXTRACTION_FAILED'
            t = db.scalar(select(ProcessingTask).where(ProcessingTask.document_id == document_id)
                          .order_by(ProcessingTask.created_at.desc()).limit(1))
            if t: t.status = 'failed'; t.error_code = doc.error_code
            db.commit()
        return 'failed'
    finally:
        if path and os.path.exists(path):
            os.unlink(path)
