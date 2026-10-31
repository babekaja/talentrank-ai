#!/usr/bin/env python3
"""Local prerequisite assessment without network calls, credentials or deployments.

This script is a read-only diagnostic and must not claim the system is production-ready.
It can be run from the repository root, without the application's Python packages.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def node_compatible(version: str) -> bool:
    m=re.match(r'^v?(\d+)\.(\d+)\.(\d+)',version)
    if not m:return False
    major,minor,patch=map(int,m.groups())
    return ((major==22 and (minor,patch)>=(22,3)) or
            (major==24 and (minor,patch)>=(15,0)) or major>=26)


def program_version(command: str, *args: str):
    if shutil.which(command) is None:
        return None
    try:
        p=subprocess.run([command,*args],capture_output=True,text=True,timeout=4,check=False)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def report() -> dict:
    node=program_version('node','--version')
    docker=program_version('docker','--version')
    required= ('fastapi','alembic','sqlalchemy','spacy','sklearn','torch','pytest')
    optional=('sentence_transformers','qdrant_client','redis','minio')
    packages={module:importlib.util.find_spec(module) is not None for module in (*required,*optional)}
    expected_paths=('apps/web/package.json','services/api/app/main.py',
                    'services/api/alembic.ini','docker-compose.yml',
                    'services/api/app/ml/neural_finetune_v13.py',
                    'services/api/app/ml/active_review_v14.py')
    present={path:(ROOT/path).is_file() for path in expected_paths}
    build_dir=ROOT/'apps/web/node_modules/@angular/core'
    return {
        'tool':'talentrank_offline_preflight_v14',
        'local_environment_only':True,
        'node_version':node,'angular22_node_supported':node_compatible(node or ''),
        'docker_binary_available':docker is not None,
        'docker_version':docker,
        'angular_dependencies_installed':build_dir.is_dir(),
        'python_packages':packages,
        'repository_files':present,
        'angular_build_verified':False,
        'docker_full_stack_verified':False,
        'pretrained_neural_model_evaluated':False,
        'production_ready':False,
        'message':('Diagnostic only. A positive prerequisite does not replace a real Angular '
                   'build, Docker/MySQL/MinIO/Qdrant integration, ML model test, security review, '
                   'licensed CV corpus or real-world fairness audit.')
    }


if __name__=='__main__':
    print(json.dumps(report(),indent=2,ensure_ascii=False))
