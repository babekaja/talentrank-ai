"""Supervised offline *threshold selection* on explicitly annotated similarity pairs.

Does not train an embedding model. Select using TRAIN only; EVALUATE held-out
rows with nonoverlapping groups. Never silently turn scores into probabilities.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import math

@dataclass(frozen=True)
class LabeledPair:
    group: str
    split: str            # train | validation
    score: float          # raw cosine from a known embedding model
    equivalent: bool     # explicit binary human annotation
    language: str


def metrics(rows: Sequence[LabeledPair], threshold: float) -> dict:
    tp = sum(r.equivalent and r.score >= threshold for r in rows)
    fp = sum(not r.equivalent and r.score >= threshold for r in rows)
    fn = sum(r.equivalent and r.score < threshold for r in rows)
    tn = sum(not r.equivalent and r.score < threshold for r in rows)
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {'tp':tp, 'fp':fp, 'fn':fn, 'tn':tn,
            'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4)}


def calibrate(rows: Sequence[LabeledPair], *, min_precision: float = 0.95) -> dict:
    if not 0 <= min_precision <= 1:
        raise ValueError('INVALID_MIN_PRECISION')
    if len(rows) < 4 or not all(r.group and r.language in ('fr','en') and
            r.split in ('train','validation') and math.isfinite(r.score) and
            -1 <= r.score <= 1 and isinstance(r.equivalent, bool) for r in rows):
        raise ValueError('INVALID_ANNOTATIONS')
    train = [r for r in rows if r.split == 'train']
    validation = [r for r in rows if r.split == 'validation']
    if not train or not validation or {r.group for r in train} & {r.group for r in validation}:
        raise ValueError('DATA_LEAKAGE_OR_MISSING_SPLIT')
    if {r.equivalent for r in train} != {True,False} or {r.equivalent for r in validation} != {True,False}:
        raise ValueError('BOTH_LABELS_REQUIRED_IN_EACH_SPLIT')
    # Thresholds at observed training values plus +epsilon (all negative);
    # validation data NEVER affects threshold selection.
    thresholds = sorted({r.score for r in train} | {min(1.000001,max(r.score for r in train)+0.000001)})
    qualified = [(t, metrics(train,t)) for t in thresholds]
    qualified = [(t,m) for t,m in qualified if m['precision'] >= min_precision and m['tp'] > 0]
    if not qualified:
        return {'selected': False, 'reason':'NO_THRESHOLD_MEETS_TRAIN_PRECISION',
                'train_size':len(train), 'validation_size':len(validation)}
    # Among feasible points, maximize train recall; prefer stricter threshold in ties.
    threshold, train_result = max(qualified, key=lambda x:(x[1]['recall'],x[0]))
    val = metrics(validation,threshold)
    languages = {lang:metrics([r for r in validation if r.language == lang],threshold)
                 for lang in ('fr','en') if any(r.language == lang for r in validation)}
    return {'selected': True, 'threshold': threshold, 'train':train_result,
            'validation':val, 'by_language':languages,
            'train_size':len(train),'validation_size':len(validation),
            'warning':'Seuil expérimental pour proposer une revue, jamais une équivalence automatique.'}
