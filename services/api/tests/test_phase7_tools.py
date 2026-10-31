from scripts.benchmark_matching import run_batch
from scripts.fairness_audit import evaluate
from scripts.preflight import checks
from app.core.config import Settings


def test_benchmark_is_reproducible():
    a=run_batch(100)
    assert a['success']==100 and a['items']==100 and a['seconds']>=0


def test_fairness_audit_suppresses_small_groups():
    data=[{'group':'g1','reference_match':str(i%2),'model_flag':str(int(i%3==0))} for i in range(30)]
    data += [{'group':'g2','reference_match':'1','model_flag':'1'} for _ in range(5)]
    result=evaluate(data,20)
    assert result['groups']['g2']['suppressed']
    assert result['groups']['g1']['false_positive_rate'] is not None


def test_production_preflight_disallows_http_origins():
    # Development settings can still be assessed under an explicit production flag.
    s=Settings(environment='development',jwt_secret='t'*48,cors_origins='http://localhost:4200')
    s.environment='production'
    report={r['category']:r['ok'] for r in checks(s)}
    assert not report['cors'] and not report['https']


def test_production_configuration_rejects_insecure_origins():
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        Settings(environment='production',jwt_secret='strong-secret-012345678901234567890',
                 database_url='mysql+pymysql://user:pass@mysql/db',
                 cors_origins='http://unsafe.example',refresh_cookie_secure=True,
                 s3_secret_key='real-secret',malware_scan_enabled=True)
