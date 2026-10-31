from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.documents.processing import process_document

@celery_app.task(name='talentrank.extract_document', bind=True, max_retries=0)
def extract_task(self, document_id: str):
    with SessionLocal() as session:
        result = process_document(document_id, session)
        if result == 'already_processing':
            # If a prior worker was lost, let its lease expire before retrying.
            raise self.retry(countdown=600, max_retries=2)
        if result in ('completed', 'needs_review'):
            try:
                nlp_task.delay(document_id)
            except Exception:
                pass  # A manual retry is available; document extraction has succeeded.
        return result


@celery_app.task(name='talentrank.analyze_document', bind=True, max_retries=1)
def nlp_task(self, document_id: str):
    from app.ml.processing import analyze_document
    with SessionLocal() as session:
        result = analyze_document(document_id, session)
        if result == 'failed':
            raise self.retry(countdown=60)
        if result in ('completed','unchanged'):
            from app.core.config import get_settings
            if get_settings().semantic_enabled:
                try: vector_task.apply_async(args=(document_id,), queue='vectors')
                except Exception: pass  # NLP success is not undone by vector queue outage.
        return result

@celery_app.task(name='talentrank.index_vectors', bind=True, max_retries=2, queue='vectors')
def vector_task(self, document_id: str):
    from sqlalchemy import select
    from app.core.config import get_settings
    from app.models import CVDocument, DocumentPage
    from app.ml.remote import ml_request
    if not get_settings().semantic_enabled:
        return 'disabled'
    with SessionLocal() as session:
        doc=session.get(CVDocument,document_id)
        if not doc or doc.status not in ('completed','needs_review'): return 'missing_or_unavailable'
        pages=session.scalars(select(DocumentPage).where(DocumentPage.document_id==doc.id)).all()
        payload={'organization_id':doc.organization_id,'document_id':doc.id,
                 'pages':[{'id':p.id,'text':p.text} for p in pages]}
    try:
        return ml_request('/private/index',payload)
    except Exception as exc:
        # Retry transient ML network failures. No CV content in exception or logs.
        raise self.retry(countdown=60) from None


@celery_app.task(name='talentrank.match_campaign', bind=True, max_retries=1, time_limit=900, soft_time_limit=870)
def matching_task(self, run_id: str):
    from app.ml.matching_service import execute_matching_run
    from app.models import MatchingRun
    with SessionLocal() as session:
        try:
            return execute_matching_run(run_id, session)
        except Exception:
            session.rollback()
            run = session.get(MatchingRun, run_id)
            if run:
                run.status = 'failed'
                run.error_code = 'PROCESSING_ERROR'
                session.commit()
            raise self.retry(countdown=90) from None
