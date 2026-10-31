"""Offline CSV evaluation. Never use real CVs without lawful approval and access control.

CSV: group,split,score,equivalent,language. Dataset split by candidate/group,
not by text pair. Scores must come from one pinned embedding model/version.
"""
import argparse
import csv
import json
from pathlib import Path
from app.ml.calibration import LabeledPair,calibrate


def run(path: Path, min_precision: float):
    with path.open('r', encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not {'group','split','score','equivalent','language'} <= set(reader.fieldnames or []):
            raise ValueError('MISSING_REQUIRED_COLUMNS')
        rows=[]
        for line in reader:
            if line['equivalent'] not in ('0','1'):
                raise ValueError('INVALID_BINARY_LABEL')
            rows.append(LabeledPair(group=line['group'], split=line['split'],
                score=float(line['score']), equivalent=line['equivalent']=='1',
                language=line['language']))
    result=calibrate(rows, min_precision=min_precision)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result

if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('dataset',type=Path)
    cli.add_argument('--min-precision',type=float,default=0.95)
    arguments=cli.parse_args()
    run(arguments.dataset,arguments.min_precision)
