"""Offline controlled robustness checks; no protected-attribute inference.

Pairwise contrasts must only vary an irrelevant, synthetic phrase. Assess
stability of *model outputs*, not fairness certification. No individual traces
are persisted, and this module is never used to rank applicants.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Contrast:
    requirement: str
    original_evidence: str
    changed_evidence: str
    contrast_type: str  # e.g. synthetic_name, location, irrelevant_sentence


def evaluate_contrasts(model, contrasts: list[Contrast],
                       *, score_class: str = 'supports',
                       change_limit: float = 0.10) -> dict:
    from app.ml.annotation import LABELS
    if (not contrasts or not 0 < change_limit <= 1 or score_class not in LABELS or
        any(not c.requirement.strip() or not c.original_evidence.strip() or
            not c.changed_evidence.strip() or c.original_evidence==c.changed_evidence or
            c.contrast_type not in {'synthetic_name','location','irrelevant_sentence'}
            for c in contrasts)):
        raise ValueError('INVALID_CONTRASTS')
    phrases=[]
    for c in contrasts:
        phrases.extend([f'critere: {c.requirement}\npassage: {c.original_evidence}',
                        f'critere: {c.requirement}\npassage: {c.changed_evidence}'])
    probs = model.predict_proba(phrases)
    classes = list(model.classes_)
    if score_class not in classes:
        raise ValueError('UNKNOWN_CLASS')
    idx=classes.index(score_class)
    changes=[]; flips=0; by_type={}
    for i,c in enumerate(contrasts):
        left,right=[float(probs[2*i+j][idx]) for j in (0,1)]
        if not all(math.isfinite(x) and 0<=x<=1 for x in (left,right)):
            raise ValueError('INVALID_MODEL_SCORES')
        delta=abs(left-right)
        changes.append(delta)
        flips+=int((left>=0.5)!=(right>=0.5))
        by_type.setdefault(c.contrast_type,[]).append(delta)
    return {'cases':len(contrasts),'mean_score_change':round(sum(changes)/len(changes),4),
            'max_score_change':round(max(changes),4),'decision_flips_at_0_5':flips,
            'changes_above_limit':sum(c > change_limit for c in changes),
            'by_contrast_type':{k:{'cases':len(v),'max_change':round(max(v),4)}
                                for k,v in sorted(by_type.items())},
            'warning':'Contrastes synthétiques uniquement : ne certifie pas l’équité du modèle.'}
