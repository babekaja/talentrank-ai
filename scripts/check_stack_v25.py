"""Diagnose REAL Docker Compose prerequisites, no simulated infrastructure pass.

Does not start infrastructure or read/print secret environment values.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

PROJECT=Path(__file__).resolve().parents[1]

def call(args:list[str],timeout:int=20)->tuple[bool,str]:
    try:
        r=subprocess.run(args,cwd=PROJECT,timeout=timeout,check=False,
                         capture_output=True,text=True)
        # Do not return stdout: docker may expose private metadata and credentials.
        return r.returncode==0, f'exit_code={r.returncode}'
    except (OSError, subprocess.TimeoutExpired) as error:
        return False,type(error).__name__


def diagnose()->dict:
    docker=shutil.which('docker')
    result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'docker_cli_installed':bool(docker),'docker_daemon_responding':False,
            'compose_installed':False,'compose_config_validated':False,
            'core_services':{},'real_full_stack_benchmark_executed':False,
            'production_approved':False}
    if not docker:
        result['blocker']='DOCKER_CLI_NOT_INSTALLED'
        return result
    result['docker_daemon_responding']=call([docker,'info','--format','{{.ServerVersion}}'])[0]
    result['compose_installed']=call([docker,'compose','version'])[0]
    if not result['docker_daemon_responding']:
        result['blocker']='DOCKER_DAEMON_UNAVAILABLE'
        return result
    if not result['compose_installed']:
        result['blocker']='DOCKER_COMPOSE_NOT_INSTALLED'
        return result
    # Only validate and enumerate when .env is present, never log its contents.
    if (PROJECT/'.env').is_file():
        result['compose_config_validated']=call([docker,'compose','config','--quiet'])[0]
    else:
        result['blocker']='LOCAL_ENV_NOT_CONFIGURED'
        return result
    if result['compose_config_validated']:
        for item in ('mysql','redis','minio','api','worker','web'):
            okay,_=call([docker,'compose','ps','--status','running','--services',item])
            result['core_services'][item]={'query_success':okay,'running_verified':False}
            if okay:
                p=subprocess.run([docker,'compose','ps','--status','running','--services',item],
                                 cwd=PROJECT,timeout=10,text=True,capture_output=True)
                result['core_services'][item]['running_verified']=item in p.stdout.split()
    result['all_core_services_running']=all(x['running_verified'] for x in result['core_services'].values()) and bool(result['core_services'])
    if not result['all_core_services_running']:
        result['blocker']='CORE_SERVICES_NOT_ALL_RUNNING'
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    status=diagnose()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))
    if not status.get('all_core_services_running'):raise SystemExit(2)

if __name__=='__main__':main()
