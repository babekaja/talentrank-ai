"""Optional supervised NON-GENERATIVE experiment for annotated skill/evidence pairs.

Explicitly offline. The learned model MUST NOT be used for hiring or to auto-confirm
skills. Data must be authorized, labeled by trained annotators, split by candidate,
and separately bias-tested before even considering deployment.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True)
class TrainingPair:
    group: str
    split: str
    requirement: str
    evidence: str
    label: int
    language: str


def train_and_evaluate(pairs: Sequence[TrainingPair]):
    """Return experimental estimator and held-out metrics; do NOT activate matching."""
    from sklearn.pipeline import make_pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

    if len(pairs) < 28:
        raise ValueError('NEED_AT_LEAST_28_ANNOTATED_PAIRS')
    if any(not x.group or x.split not in ('train', 'validation') or x.language not in ('fr','en')
           or x.label not in (0,1) or not x.requirement.strip() or not x.evidence.strip()
           or len(x.requirement)>500 or len(x.evidence)>1000 for x in pairs):
        raise ValueError('INVALID_ANNOTATIONS')
    train=[p for p in pairs if p.split=='train']
    val=[p for p in pairs if p.split=='validation']
    if len(train)<20 or len(val)<8 or {p.group for p in train}&{p.group for p in val}:
        raise ValueError('INSUFFICIENT_SPLIT_OR_GROUP_LEAKAGE')
    if any({p.label for p in group}!={0,1} for group in (train,val)):
        raise ValueError('EACH_SPLIT_NEEDS_BOTH_CLASSES')
    # Prevent same exact text pair being copied to holdout under a different group.
    input_pair=lambda p:(p.requirement.casefold().strip(),p.evidence.casefold().strip())
    if {input_pair(p) for p in train} & {input_pair(p) for p in val}:
        raise ValueError('DUPLICATE_PAIR_ACROSS_SPLITS')
    feature=lambda p:p.requirement.strip() + ' [CRITERION] ' + p.evidence.strip()
    clf=make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,
                         max_features=25000, sublinear_tf=True),
                      LogisticRegression(class_weight='balanced',max_iter=1000,random_state=42))
    clf.fit([feature(p) for p in train],[p.label for p in train])
    scores=clf.predict_proba([feature(p) for p in val])[:,1]
    predictions=[int(score>=0.5) for score in scores]
    truth=[p.label for p in val]
    def score_report(y_true,y_pred):
        precision,recall,f1,_=precision_recall_fscore_support(y_true,y_pred,
                     average='binary',zero_division=0)
        tn,fp,fn,tp=confusion_matrix(y_true,y_pred,labels=[0,1]).ravel()
        return {'precision':round(float(precision),4),'recall':round(float(recall),4),
                'f1':round(float(f1),4),'tp':int(tp),'fp':int(fp),'fn':int(fn),'tn':int(tn)}
    by_language={}
    for language in sorted({p.language for p in val}):
        indices=[i for i,p in enumerate(val) if p.language==language]
        by_language[language]=score_report([truth[i] for i in indices],
                                           [predictions[i] for i in indices])
    return clf, {'train_pairs':len(train),'validation_pairs':len(val),
                 'model':'tfidf_char_wb_3_5_plus_logistic_regression',
                 'heldout':score_report(truth,predictions),'by_language':by_language,
                 'warning':'Expérience supervisée hors production. Scores non utilisables pour une décision RH.'}
