"""V10 conservative research-only positive-prediction precision guard.

Wilson LOWER BOUND over reviewed calibration outcomes, not a mean score.
No use for employment decisions, no evidence of generalization by itself.
"""
from __future__ import annotations
import math
from typing import Sequence

from app.ml.pair_classifier import wilson_interval


def choose_research_threshold(labels: Sequence[str], support_scores: Sequence[float], *,
                              min_precision_lower_bound: float = .90,
                              min_selected: int = 30) -> dict:
    if (len(labels)!=len(support_scores) or not 0<min_precision_lower_bound<1 or
        not 2<=min_selected or any(l not in ('supports','related','insufficient') for l in labels) or
        any(not math.isfinite(float(s)) or not 0<=float(s)<=1 for s in support_scores)):
        raise ValueError('INVALID_GATE_CALIBRATION')
    accepted=[]
    for threshold in sorted(set(float(s) for s in support_scores)):
        selected=[i for i,score in enumerate(support_scores) if score>=threshold]
        if len(selected)<min_selected:continue
        tp=sum(labels[i]=='supports' for i in selected)
        ci=wilson_interval(tp,len(selected))
        if ci is not None and ci[0]>=min_precision_lower_bound:
            accepted.append((len(selected),threshold,tp,ci))
    if not accepted:
        return {'enabled':False,'threshold':None,'selected':0,
                'reason':'INSUFFICIENT_CALIBRATION_EVIDENCE',
                'min_selected':min_selected,'required_wilson_lower95':min_precision_lower_bound}
    count,cutoff,tp,ci=max(accepted,key=lambda r:(r[0],r[1]))
    return {'enabled':True,'threshold':cutoff,'selected':count,
            'observed_precision':round(tp/count,4),'precision_wilson95':ci,
            'required_wilson_lower95':min_precision_lower_bound,
            'note':'Research-only confidence bound on calibration labels; not proof of real-world precision.'}
