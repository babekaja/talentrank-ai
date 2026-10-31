"""Run a reproducible off-line supervised experiment on a user-authorized CSV.

Never supplies this model to the live matching engine. No auto-training on recruiter
historical decisions. Does not persist the input CV texts, labels or model by default.
"""
import argparse
import csv
import json
from pathlib import Path
from app.ml.supervised import TrainingPair, train_and_evaluate


def run(path: Path):
    with path.open('r',encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        mandatory={'group','split','requirement','evidence','equivalent','language'}
        if not mandatory <= set(reader.fieldnames or []):
            raise ValueError('MISSING_COLUMNS')
        pairs=[]
        for row in reader:
            if row['equivalent'] not in ('0','1'):
                raise ValueError('INVALID_BINARY_LABEL')
            pairs.append(TrainingPair(row['group'],row['split'],row['requirement'],
                                      row['evidence'],int(row['equivalent']),row['language']))
    _,report=train_and_evaluate(pairs)
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('dataset',type=Path)
    args=parser.parse_args()
    run(args.dataset)
