"""Validate two separately returned annotation CSVs, without pretending identities are verified.

Requires explicit external reviewer attestations and provenance documents for claims
of independent annotations. Never emits raw personal CV text in the output report.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

LABELS={'supports','related','insufficient'}


def load_csv(path:Path):
    with path.open('r',newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if not rows or len({r['task_id'] for r in rows})!=len(rows):
        raise ValueError('EMPTY_OR_DUPLICATE_TASKS')
    if not all(r['reviewer_label'] in LABELS for r in rows):
        raise ValueError('INCOMPLETE_OR_INVALID_LABELS')
    return {r['task_id']:r for r in rows}


def assess(path_a:Path,path_b:Path, *, reviewer_a:str,reviewer_b:str):
    if not reviewer_a.strip() or not reviewer_b.strip() or reviewer_a==reviewer_b:
        raise ValueError('TWO_DISTINCT_REVIEWER_IDENTITIES_REQUIRED')
    a=load_csv(path_a);b=load_csv(path_b)
    if set(a)!=set(b):raise ValueError('TASK_SET_MISMATCH')
    for key in a:
        for field in ('doc_id','split','language','criterion','passage'):
            if a[key][field]!=b[key][field]:raise ValueError('ALTERED_TASK_CONTENT')
    agrees=[k for k in a if a[k]['reviewer_label']==b[k]['reviewer_label']]
    disagree=[k for k in a if k not in agrees]
    cats=sorted(LABELS)
    counts_a=Counter(row['reviewer_label'] for row in a.values()); counts_b=Counter(row['reviewer_label'] for row in b.values())
    observed=len(agrees)/len(a)
    expected=sum(counts_a[c]*counts_b[c] for c in cats)/(len(a)**2)
    kappa=(observed-expected)/(1-expected) if expected<1 else None
    return {'task_count':len(a),'agreements':len(agrees),'disagreements':len(disagree),
            'agreement_rate':round(observed,4), 'cohen_kappa':round(kappa,4) if kappa is not None else None,
            'reviewer_ids':[reviewer_a,reviewer_b],
            'disagreement_task_ids':sorted(disagree),
            'annotation_integrity':'structural_only_reviewers_not_identity_verified',
            'requires_independent_identity_attestation':True,
            'requires_adjudication':bool(disagree),
            'human_independence_certified':False,
            'source_digests':[sha256(p.read_bytes()).hexdigest() for p in (path_a,path_b)]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a',type=Path,required=True)
    parser.add_argument('--b',type=Path,required=True)
    parser.add_argument('--reviewer-a',required=True)
    parser.add_argument('--reviewer-b',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=assess(args.a,args.b,reviewer_a=args.reviewer_a,reviewer_b=args.reviewer_b)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'report':str(args.output),'agreements':result['agreements'],
                      'requires_adjudication':result['requires_adjudication']}))

if __name__=='__main__':main()
