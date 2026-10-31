"""Offline fairness evaluation. Accept only authorized annotated data; no storage in DB.

Example: python -m scripts.fairness_lab_v24 --pairs path.json --aliases aliases.json --output output.json
"""
import argparse
import json
from pathlib import Path
from app.ml.fairness_lab_v24 import paired_audit, group_audit

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--pairs', type=Path)
    cli.add_argument('--groups', type=Path)
    cli.add_argument('--aliases', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--min-group-size', type=int, default=10)
    opts = cli.parse_args()
    if not (opts.pairs or opts.groups):
        cli.error('At least one evaluation input required')
    output = {'release_gate':'not_certified'}
    if opts.pairs:
        if not opts.aliases:
            cli.error('--aliases needed to execute real recognition for counterfactual pairs')
        output['counterfactual'] = paired_audit(json.loads(opts.pairs.read_text()),
                                                json.loads(opts.aliases.read_text()))
    if opts.groups:
        output['group_audit'] = group_audit(json.loads(opts.groups.read_text()),
                                            min_group_size=opts.min_group_size)
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'output':str(opts.output),'release_gate':'not_certified'},ensure_ascii=False))

if __name__ == '__main__': main()
