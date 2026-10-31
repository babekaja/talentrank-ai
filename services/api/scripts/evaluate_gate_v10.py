"""V10: compare legacy calibration point estimate with Wilson lower-bound guard.

Only synthetic/consented annotation experiments. No applicant ranking changes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from app.ml.annotation import load_gold
from app.ml.pair_classifier import pair_text,train_experiment
from app.ml.confidence_gate import choose_research_threshold


def run(path: Path, *, output: Path|None=None,
        min_precision_lower_bound:float=.90, min_selected:int=30):
    rows, dataset=load_gold(path)
    estimator, old=train_experiment(rows)
    calibration=[row for row in rows if row.split=='calibration']
    test=[row for row in rows if row.split=='test']
    columns=list(estimator.classes_)
    support=columns.index('supports')
    scores=estimator.predict_proba([pair_text(p) for p in calibration])
    guard=choose_research_threshold([p.label for p in calibration],
            [float(row[support]) for row in scores],
            min_precision_lower_bound=min_precision_lower_bound,min_selected=min_selected)
    # The untouched TEST split is read once for research metrics; NEVER select threshold here.
    test_probs=estimator.predict_proba([pair_text(p) for p in test])
    if guard['enabled']:
        threshold=guard['threshold']
        suggestions=[(row.label,float(pred[support])) for row,pred in zip(test,test_probs)
                     if float(pred[support])>=threshold]
    else:
        suggestions=[]
    tp=sum(label=='supports' for label,_ in suggestions)
    result={'experiment':'triage_conservative_gate_v10','dataset_sha256':dataset['dataset_sha256'],
        'calibration_samples':len(calibration),'test_samples':len(test),
        'legacy_calibration':old['calibration'],'v10_wilson_guard':guard,
        'test_suggestions':len(suggestions),'test_false_support_suggestions':len(suggestions)-tp,
        'test_precision':round(tp/len(suggestions),4) if suggestions else None,
        'test_abstentions':len(test)-len(suggestions),
        'note':'Research only. Calibration and test never mixed; no person-level outputs.'}
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--min-precision-lower-bound',type=float,default=.90)
    p.add_argument('--min-selected',type=int,default=30)
    a=p.parse_args()
    run(a.dataset,output=a.output,min_precision_lower_bound=a.min_precision_lower_bound,
        min_selected=a.min_selected)
