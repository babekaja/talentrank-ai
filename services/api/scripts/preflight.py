"""Environment safety checks without printing credentials or candidate data.

Run: python -m scripts.preflight [--check-services]
"""
import argparse
import sys
from app.core.config import get_settings


def checks(settings, *, check_services=False):
    messages=[]
    def flag(ok,category,detail):messages.append({'ok':bool(ok),'category':category,'detail':detail})
    production=settings.environment=='production'
    flag(len(settings.jwt_secret)>=32 and not settings.jwt_secret.startswith(('REPLACE_','CHANGE_')),
         'secrets','Secret JWT configured')
    flag(not production or settings.database_url.startswith('mysql+pymysql://'),
         'database','Production uses MySQL')
    flag(not production or settings.refresh_cookie_secure,
         'https','Secure refresh cookie enforced')
    flag(not production or (settings.origins and all(origin.startswith('https://') for origin in settings.origins)),
         'cors','Production CORS uses HTTPS-only origins')
    flag(not production or settings.malware_scan_enabled,
         'antivirus','File scanning required in production')
    flag(not production or not settings.semantic_enabled or not settings.ml_service_token.startswith('CHANGE_'),
         'vector','Internal semantic token configured')
    flag(not production or not settings.candidate_portal_enabled or (
        bool(settings.candidate_portal_smtp_host) and bool(settings.candidate_portal_from_email)
        and settings.candidate_portal_base_url.startswith('https://')),
        'candidate-email','Candidate portal needs verified SMTP and HTTPS origin')
    if check_services:
        from sqlalchemy import text
        from app.core.database import build_engine
        try:
            engine=build_engine()
            with engine.connect() as c:c.execute(text('SELECT 1'))
            engine.dispose()
            flag(True,'database-reachable','Database connection successful')
        except Exception:flag(False,'database-reachable','Database is unavailable')
        try:
            from redis import Redis
            cache=Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
            flag(bool(cache.ping()), 'redis-reachable', 'Redis responds to PING (worker processing unverified)')
        except Exception:flag(False,'redis-reachable','Redis is unavailable')
        if settings.malware_scan_enabled:
            from app.documents.malware import scanner_health
            flag(scanner_health(settings.clamav_host, settings.clamav_port),
                 'clamav-reachable','ClamAV must answer the actual PING protocol')
        if settings.semantic_enabled:
            try:
                from qdrant_client import QdrantClient
                client=QdrantClient(url=settings.qdrant_url, timeout=3)
                client.get_collections()
                flag(True,'qdrant-reachable','Vector DB responds (neural model unverified)')
            except Exception:flag(False,'qdrant-reachable','Vector DB is unavailable')
        try:
            from app.documents.storage import PrivateStorage
            from minio.error import S3Error
            private=PrivateStorage()
            exists=bool(private.client.bucket_exists(private.bucket))
            flag(exists,'storage-reachable','Private bucket exists')
            if exists:
                try:
                    # Reject ANY bucket policy: a private bucket needs no public policy.
                    private.client.get_bucket_policy(private.bucket)
                    flag(False,'storage-private','Bucket policy present: review and remove public access')
                except S3Error as exc:
                    flag(exc.code=='NoSuchBucketPolicy','storage-private',
                         'No public bucket policy' if exc.code=='NoSuchBucketPolicy' else 'Policy inspection failed')
                except Exception:
                    flag(False,'storage-private','Could not verify bucket access policy')
        except Exception:flag(False,'storage-reachable','Private storage is unavailable')
        try:
            from app.workers.celery_app import celery_app
            answers=celery_app.control.ping(timeout=5) or []
            flag(bool(answers),'celery-workers','At least one Celery worker answers ping (task execution unverified)')
        except Exception:flag(False,'celery-workers','No Celery worker is responding')
    return messages


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-services',action='store_true')
    args=parser.parse_args()
    try:settings=get_settings()
    except Exception:
        print('FAIL settings: configuration invalid (credentials hidden)')
        sys.exit(1)
    evaluations=checks(settings,check_services=args.check_services)
    for x in evaluations:print(('PASS' if x['ok'] else 'FAIL')+' '+x['category']+': '+x['detail'])
    print(f"SUMMARY {sum(x['ok'] for x in evaluations)}/{len(evaluations)}")
    sys.exit(0 if all(x['ok'] for x in evaluations) else 1)

if __name__=='__main__':main()
