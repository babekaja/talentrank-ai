from celery import Celery
from celery.signals import worker_process_init
from app.core.config import get_settings

celery_app = Celery('talentrank', broker=get_settings().redis_url)
celery_app.conf.update(task_serializer='json', accept_content=['json'],
    task_acks_late=True, worker_prefetch_multiplier=1, task_reject_on_worker_lost=True,
    task_track_started=True, task_time_limit=180, task_soft_time_limit=160)
celery_app.autodiscover_tasks(['app.workers'])
celery_app.conf.imports = ('app.workers.tasks',)


@worker_process_init.connect
def reset_database_pool_after_fork(**_kwargs):
    """Never let prefork children share a database socket inherited by the parent."""
    from app.core.database import engine
    engine.dispose(close=False)
