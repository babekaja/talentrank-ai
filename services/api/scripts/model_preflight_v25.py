"""Test true LOCAL model availability without downloads or experimental substitution."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from importlib.util import find_spec


def check(path:Path|None)->dict:
    installed=find_spec('sentence_transformers') is not None
    loaded = path is not None and path.is_dir() and (path/'modules.json').is_file()
    return {'sentence_transformers_installed':installed,
            'local_model_directory_valid':loaded,
            'pretrained_neural_inference_executed':False,
            'evaluation_on_independent_human_labels':False,
            'deployment_enabled':False,
            'ready_for_real_model_benchmark':bool(installed and loaded),
            'blocker':('SENTENCE_TRANSFORMERS_NOT_INSTALLED' if not installed else
                       'LOCAL_PRETRAINED_MODEL_NOT_AVAILABLE' if not loaded else None)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local-model',type=Path)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    result=check(args.local_model)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    if not result['ready_for_real_model_benchmark']:raise SystemExit(2)

if __name__=='__main__':main()
