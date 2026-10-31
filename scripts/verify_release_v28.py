"""Non-destructive production-readiness diagnostic. Never declares CV/ML validated.

Run on a machine with Docker installed after `docker compose up -d`.
The optional smoke touches only a DEDICATED fictional test organisation.
No secrets or CV text are written to the report.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from check_stack_v25 import diagnose, PROJECT


def docker_exec(*args: str, timeout:int=60) -> bool:
    try:
        proc=subprocess.run(['docker','compose','exec','-T','api',*args], cwd=PROJECT,
                stdin=subprocess.DEVNULL, text=True,capture_output=True,timeout=timeout)
        return proc.returncode==0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run(run_smoke:bool=False) -> dict:
    stack=diagnose()
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'stack':stack,'checks':{},'browser_tests':'NOT_RUN',
        'neural_accuracy':'NOT_VALIDATED', 'fairness':'NOT_VALIDATED',
        'end_to_end_3000_cv':'NOT_RUN','production_approved':False}
    if not stack.get('all_core_services_running'):
        report['blocker']=stack.get('blocker','STACK_NOT_VERIFIED'); return report
    report['checks']['api_readiness']=docker_exec('python','-c',
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=8)")
    report['checks']['alembic_schema']=docker_exec('alembic','check')
    report['checks']['service_readiness']=docker_exec('python','-m','scripts.preflight','--check-services')
    if run_smoke:
        required=('TR_SMOKE_URL','TR_SMOKE_ORG','TR_SMOKE_EMAIL','TR_SMOKE_PASSWORD')
        if not all(os.environ.get(k) for k in required):
            report['checks']['synthetic_journey']=False
            report['blocker']='MISSING_SYNTHETIC_SMOKE_CREDENTIALS'
        else:
            try:
                cp=subprocess.run([sys.executable,'-m','scripts.smoke_stack_v18'],
                    cwd=PROJECT/'services/api',capture_output=True,text=True,timeout=420)
                report['checks']['synthetic_journey']=cp.returncode==0
            except (OSError,subprocess.TimeoutExpired):
                report['checks']['synthetic_journey']=False
    if not all(report['checks'].values()):
        report['blocker']=report.get('blocker','REAL_SERVICE_CHECK_FAILED')
    else:
        report['blocker']='ML_FAIRNESS_LOAD_AND_BROWSER_EVIDENCE_MISSING'
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('docs/benchmarks/real-stack-v28.json'))
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    result=run(args.smoke)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'blocker':result['blocker'],'checks':result['checks'],
                      'production_approved':False},ensure_ascii=False))
    sys.exit(2 if result.get('blocker') else 0)

if __name__=='__main__': main()
