"""Selectively predictive 3-class ML EXPERIMENT for requirement/evidence pairs.

Only for expert-labelled OFFLINE evaluation. Never integrated with TalentRank's
matching engine, applicant ranking, automated selection or rejection. The
validation split selects the abstention threshold; the untouched test split
reports its transfer. Scores are NOT competence or employability probabilities.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Sequence

from app.ml.annotation import GoldPair, LABELS, SPLITS

MODEL_NAME = 'tfidf_word_char_lr_3class_v1'


def pair_text(p: GoldPair) -> str:
    # Crucial: concatenate in a stable, explicit order to avoid train/infer skew.
    return f'critere: {p.requirement.strip()}\npassage: {p.evidence.strip()}'


def class_metrics(gold: Sequence[str], predictions: Sequence[str]) -> dict:
    if len(gold) != len(predictions):
        raise ValueError('PREDICTION_LENGTH_MISMATCH')
    results = {}
    for label in LABELS:
        tp = sum(a == label and b == label for a, b in zip(gold, predictions))
        fp = sum(a != label and b == label for a, b in zip(gold, predictions))
        fn = sum(a == label and b != label for a, b in zip(gold, predictions))
        precision = tp/(tp+fp) if tp+fp else 0.0
        recall = tp/(tp+fn) if tp+fn else 0.0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
        results[label] = {'support': sum(a == label for a in gold), 'tp':tp, 'fp':fp, 'fn':fn,
                          'precision':round(precision,4), 'recall':round(recall,4),
                          'f1':round(f1,4)}
    results['macro_f1'] = round(sum(results[k]['f1'] for k in LABELS)/len(LABELS), 4)
    return results


def select_threshold(gold: Sequence[str], probabilities,
                     classes: Sequence[str], *, min_precision: float = 0.9,
                     min_positive_predictions: int = 2) -> dict:
    """Select threshold on CALIBRATION only for suggesting supports-for-review.

    Never use test, and never use predicted 'related' to auto-reject someone.
    """
    if not 0 < min_precision <= 1 or min_positive_predictions < 1:
        raise ValueError('INVALID_CALIBRATION_PARAMETERS')
    if 'supports' not in classes or len(gold) != len(probabilities):
        raise ValueError('INVALID_CALIBRATION_DATA')
    index = list(classes).index('supports')
    support_scores = [float(row[index]) for row in probabilities]
    if any(not math.isfinite(score) or not 0 <= score <= 1 for score in support_scores):
        raise ValueError('NON_FINITE_SCORES')
    feasible = []
    for threshold in sorted(set(support_scores)):
        selected = [i for i, score in enumerate(support_scores) if score >= threshold]
        if len(selected) < min_positive_predictions:
            continue
        tp = sum(gold[i] == 'supports' for i in selected)
        precision = tp / len(selected)
        if precision >= min_precision:
            feasible.append((len(selected), threshold, tp, precision))
    if not feasible:
        return {'selected':False,'reason':'NO_CALIBRATED_THRESHOLD',
                'min_precision_requested':min_precision}
    _, threshold, tp, precision = max(feasible, key=lambda r:(r[0],r[1]))
    return {'selected':True, 'support_threshold':float(threshold),
            'calibration_precision':round(precision, 4),
            'calibration_true_positives':tp,
            'min_precision_requested':min_precision}


def probability_diagnostics(gold: Sequence[str], probabilities, classes: Sequence[str],
                            *, bins: int = 8) -> dict:
    """Multiclass Brier score + coarse ECE for LABEL predictions only.

    Reliability here concerns annotation labels, *not* suitability for hiring.
    With small samples this estimate is unstable and must not be overinterpreted.
    """
    if not gold or len(gold)!=len(probabilities) or set(classes)!=set(LABELS) or not 2<=bins<=20:
        raise ValueError('INVALID_DIAGNOSTIC_INPUT')
    index={label:i for i,label in enumerate(classes)}
    brier=0.0; buckets=[[] for _ in range(bins)]
    for truth,row in zip(gold,probabilities):
        if truth not in LABELS or len(row)!=len(classes):
            raise ValueError('INVALID_DIAGNOSTIC_INPUT')
        values=[float(v) for v in row]
        if any(not math.isfinite(v) or v<0 or v>1 for v in values) or abs(sum(values)-1)>1e-3:
            raise ValueError('INVALID_PROBABILITIES')
        brier+=sum((score-int(i==index[truth]))**2 for i,score in enumerate(values))
        top=max(range(len(values)),key=lambda i:values[i])
        confidence=values[top]
        bucket=min(bins-1,int(confidence*bins))
        buckets[bucket].append((confidence,int(classes[top]==truth)))
    n=len(gold)
    ece=sum(len(group)/n*abs(sum(c for c,_ in group)/len(group)-
                  sum(hit for _,hit in group)/len(group)) for group in buckets if group)
    return {'multiclass_brier':round(brier/n,4),
            'expected_calibration_error':round(ece,4),'bins':bins,
            'warning':'Diagnostic instable sur petits jeux, ne mesure pas la probabilité d’embauche.'}


def wilson_interval(successes: int, trials: int, *, z: float = 1.96) -> list[float] | None:
    """Approximate 95% Wilson binomial CI; None when no selected examples."""
    if trials == 0:
        return None
    if trials < 0 or not 0 <= successes <= trials:
        raise ValueError('INVALID_BINOMIAL_COUNTS')
    p = successes/trials
    denom = 1 + z*z/trials
    center = (p + z*z/(2*trials))/denom
    radius = z * math.sqrt(p*(1-p)/trials+z*z/(4*trials*trials))/denom
    return [round(max(0,center-radius),4),round(min(1,center+radius),4)]


def evaluate_selective(rows: Sequence[GoldPair], probabilities,
                       classes: Sequence[str], threshold: float | None) -> dict:
    """Triage with abstention. All labels remain suggestions for human review."""
    if len(rows) != len(probabilities):
        raise ValueError('PREDICTION_LENGTH_MISMATCH')
    if threshold is not None and not 0 <= threshold <= 1:
        raise ValueError('INVALID_THRESHOLD')
    idx = {name:i for i, name in enumerate(classes)}
    if set(idx) != set(LABELS):
        raise ValueError('INVALID_CLASSES')
    triage, gold, confidence = [], [], []
    for item, scores in zip(rows, probabilities):
        values = [float(scores[idx[c]]) for c in LABELS]
        if any(not math.isfinite(s) or not 0 <= s <= 1 for s in values):
            raise ValueError('NON_FINITE_SCORES')
        if abs(sum(values) - 1.0) > 1e-3:
            raise ValueError('SCORES_NOT_NORMALIZED')
        label_index = max(range(len(values)), key=lambda i:values[i])
        label = LABELS[label_index]
        predicted = ('supports_suggestion' if threshold is not None and
                     label == 'supports' and values[0] >= threshold else 'human_review')
        triage.append(predicted)
        gold.append(item.label)
        confidence.append(values[0])
    tp=sum(g == 'supports' and p == 'supports_suggestion' for g,p in zip(gold,triage))
    fp=sum(g != 'supports' and p == 'supports_suggestion' for g,p in zip(gold,triage))
    fn=sum(g == 'supports' and p != 'supports_suggestion' for g,p in zip(gold,triage))
    n_select=tp+fp
    report={'pairs':len(rows),'suggestions':n_select,'abstentions':len(rows)-n_select,
            'suggestion_precision':round(tp/n_select,4) if n_select else None,
            'suggestion_precision_wilson95':wilson_interval(tp,n_select),
            'suggestion_recall':round(tp/(tp+fn),4) if tp+fn else None,
            'false_support_suggestions':fp}
    return report


def train_experiment(pairs: Sequence[GoldPair], *, min_precision: float = 0.9) -> tuple[object, dict]:
    """Fit train only, calibrate only on calibration, evaluate once on untouched test."""
    from sklearn.pipeline import Pipeline, FeatureUnion
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    by_split = {s:[p for p in pairs if p.split == s] for s in SPLITS}
    if not (len(by_split['train']) >= 24 and len(by_split['calibration']) >= 9
            and len(by_split['test']) >= 9):
        raise ValueError('INSUFFICIENT_THREE_WAY_SPLIT')
    groups = {s:{p.candidate_group for p in by_split[s]} for s in SPLITS}
    docs = {s:{p.document_group for p in by_split[s]} for s in SPLITS}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i+1:]:
            if groups[a] & groups[b] or docs[a] & docs[b]:
                raise ValueError('GROUP_SPLIT_LEAKAGE')
            left={(p.requirement.strip().casefold(),p.evidence.strip().casefold()) for p in by_split[a]}
            right={(p.requirement.strip().casefold(),p.evidence.strip().casefold()) for p in by_split[b]}
            if left & right:
                raise ValueError('TEXT_SPLIT_LEAKAGE')
    if any(set(p.label for p in by_split[s]) != set(LABELS) for s in SPLITS):
        raise ValueError('EACH_SPLIT_REQUIRES_THREE_CLASSES')
    for split in SPLITS:
        if any(p.language not in ('fr','en') or not p.requirement.strip() or
               not p.evidence.strip() or p.label not in LABELS for p in by_split[split]):
            raise ValueError('INVALID_PAIR')
    estimator = Pipeline([
      ('features', FeatureUnion([
          ('words', TfidfVectorizer(ngram_range=(1,2), strip_accents='unicode',
                      lowercase=True, sublinear_tf=True, max_features=25000)),
          ('chars', TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),
                      strip_accents='unicode', lowercase=True, sublinear_tf=True,
                      max_features=30000))])),
      ('classifier', LogisticRegression(class_weight='balanced', max_iter=1200,
                      random_state=42, solver='lbfgs'))])
    train=by_split['train']; calibration=by_split['calibration']; test=by_split['test']
    estimator.fit([pair_text(p) for p in train], [p.label for p in train])
    classes=list(estimator.classes_)
    calib_probs=estimator.predict_proba([pair_text(p) for p in calibration])
    cutoff=select_threshold([p.label for p in calibration],calib_probs,classes,
                            min_precision=min_precision)
    test_probs=estimator.predict_proba([pair_text(p) for p in test])
    test_preds=list(estimator.predict([pair_text(p) for p in test]))
    threshold=cutoff['support_threshold'] if cutoff['selected'] else None
    breakdown={}
    for lang in ('fr','en'):
        indices=[i for i,p in enumerate(test) if p.language == lang]
        if indices:
            breakdown[lang]={
               'classification':class_metrics([test[i].label for i in indices],
                                              [test_preds[i] for i in indices]),
               'selective':evaluate_selective([test[i] for i in indices],
                                             test_probs[indices],classes,threshold)}
    result={'model':MODEL_NAME,'training_samples':len(train),'calibration_samples':len(calibration),
            'test_samples':len(test),'classes':list(LABELS),'train_only_fit':True,
            'calibration':cutoff,
            'test':{'classification':class_metrics([p.label for p in test],test_preds),
                    'selective':evaluate_selective(test,test_probs,classes,threshold),
                    'probability_diagnostics':probability_diagnostics([p.label for p in test],test_probs,classes),
                    'by_language':breakdown},
            'warning':'Évaluation hors production. Aucun modèle entraîné sur données synthétiques ne doit être utilisé en recrutement.'}
    return estimator,result



def propose_pair_review(estimator, calibration: dict, requirement: str,
                        evidence: str) -> dict:
    """OFFLINE research-only single-pair triage. No credibility, skills, or hiring score.

    Only manually supplied source evidence. No source citation can be invented;
    provenance must be checked by the caller against the original document.
    """
    if not (2<=len(requirement.strip())<=500 and 3<=len(evidence.strip())<=1000):
        raise ValueError('INVALID_PAIR_INPUT')
    if not calibration.get('selected'):
        return {'status':'human_review','reason':'UNVALIDATED_MODEL_THRESHOLD',
                'note':'Aucun résultat ML admis sans calibration valide.'}
    cutoff=calibration.get('support_threshold')
    if not isinstance(cutoff, (float,int)) or not 0<=cutoff<=1:
        raise ValueError('INVALID_THRESHOLD')
    source=f'critere: {requirement.strip()}\npassage: {evidence.strip()}'
    scores=estimator.predict_proba([source])[0]
    classes=list(estimator.classes_)
    if 'supports' not in classes:
        raise ValueError('MODEL_MISSING_SUPPORTS')
    support_score=float(scores[classes.index('supports')])
    top=classes[max(range(len(classes)),key=lambda i:float(scores[i]))]
    if not math.isfinite(support_score) or not 0<=support_score<=1:
        raise ValueError('INVALID_MODEL_OUTPUT')
    suggested=top=='supports' and support_score>=cutoff
    return {'status':'supports_suggestion_to_review' if suggested else 'human_review',
            'reason':'THRESHOLD_REACHED' if suggested else 'NOT_CALIBRATED_SUPPORT',
            'note':'Signal ML expérimental, jamais preuve automatique de compétence.',
            'model':MODEL_NAME}
