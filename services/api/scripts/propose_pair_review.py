"""Offline demo only. No API, no ranking, no persistence of user input."""
import argparse
import json
from pathlib import Path
from app.ml.annotation import load_gold
from app.ml.pair_classifier import train_experiment,propose_pair_review


def run(dataset: Path, requirement: str, evidence: str):
    gold,_=load_gold(dataset)
    estimator,report=train_experiment(gold)
    result=propose_pair_review(estimator,report['calibration'],requirement,evidence)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    cli=argparse.ArgumentParser(description='RESEARCH ONLY: human-review proposal, no automated decisions')
    cli.add_argument('dataset',type=Path)
    cli.add_argument('--requirement',required=True)
    cli.add_argument('--evidence',required=True)
    args=cli.parse_args();run(args.dataset,args.requirement,args.evidence)
