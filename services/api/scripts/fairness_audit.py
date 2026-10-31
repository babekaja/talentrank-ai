"""Offline audit on separately collected, legally authorized annotations.

No demographic inference. No clinical/identity information included in output.
Required CSV columns: group, reference_match, model_flag; values for latter 0 or 1.
Groups with fewer than min-size observations are suppressed.
A flagged score is not an employment decision; this evaluates a selected cutoff only.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def evaluate(records, min_size=20):
    grouped=defaultdict(list)
    for record in records:
        group=record['group'].strip()
        if record['reference_match'] not in ('0','1') or record['model_flag'] not in ('0','1'):
            raise ValueError('reference_match and model_flag must be 0 or 1')
        if not group:raise ValueError('Empty group')
        grouped[group].append((int(record['reference_match']),int(record['model_flag'])))
    result={}
    for group,rows in sorted(grouped.items()):
        if len(rows)<min_size:
            result[group]={'n':len(rows),'suppressed':True}
            continue
        fp=sum(truth==0 and prediction==1 for truth,prediction in rows)
        tn=sum(truth==0 and prediction==0 for truth,prediction in rows)
        fn=sum(truth==1 and prediction==0 for truth,prediction in rows)
        tp=sum(truth==1 and prediction==1 for truth,prediction in rows)
        result[group]={'n':len(rows),'suppressed':False,
            'false_positive_rate':round(fp/(fp+tn),4) if fp+tn else None,
            'false_negative_rate':round(fn/(fn+tp),4) if fn+tp else None,
            'precision':round(tp/(tp+fp),4) if tp+fp else None,
            'recall':round(tp/(tp+fn),4) if tp+fn else None}
    return {'groups':result,'disclaimer':('These metrics do not prove fairness and must be interpreted '
        'with measurement uncertainty, provenance, legality, and human review.')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('annotations',type=Path)
    parser.add_argument('--min-size',type=int,default=20)
    args=parser.parse_args()
    if args.min_size<10:parser.error('min-size must be at least 10')
    with args.annotations.open(newline='',encoding='utf-8-sig') as handle:
        raw=list(csv.DictReader(handle))
    print(json.dumps(evaluate(raw,args.min_size),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
