"""Counterfactual and group fairness research, not a fairness certification.

Only provided, lawfully collected labels may be analyzed. Never infer identity or
protected attributes from names. Do not emit candidate-level predictions or raw text.
"""
from collections import defaultdict
from hashlib import sha256
import json
import math
from statistics import mean
from app.ml.recognition import extract_mentions

SENSITIVE_CONTEXTS = {'identity','address_proxy','school_prestige','employment_gap','informal_experience'}


def signature(text: str, aliases: list[tuple[str, str, str]]) -> set[tuple[str, str]]:
    return {(x.skill_id, x.status) for x in extract_mentions(text, aliases)}


def paired_audit(cases: list[dict], aliases: list[tuple[str,str,str]]) -> dict:
    """A difference is a warning to investigate, not automatic proof of discrimination."""
    if not cases or len(cases) > 1000:
        raise ValueError('REQUIRES_BOUNDED_ANNOTATED_PAIRS')
    summary = defaultdict(lambda: {'count':0, 'changed':0, 'removed':0, 'added':0})
    seen = set()
    for row in cases:
        kind = row['variation_type']
        if kind not in SENSITIVE_CONTEXTS:
            raise ValueError('INVALID_VARIATION_TYPE')
        case_id = str(row['pair_id'])
        if case_id in seen:
            raise ValueError('DUPLICATE_PAIR_ID')
        seen.add(case_id)
        a, b = row['original_text'], row['variant_text']
        if not 5 <= len(a) <= 6000 or not 5 <= len(b) <= 6000:
            raise ValueError('INVALID_PROFESSIONAL_TEXT')
        first = signature(a, aliases)
        second = signature(b, aliases)
        agg = summary[kind]
        agg['count'] += 1
        agg['changed'] += first != second
        agg['removed'] += len(first-second)
        agg['added'] += len(second-first)
    counts = {k:dict(v) for k,v in sorted(summary.items())}
    digest = sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {'dataset_sha256':digest, 'pairs':len(seen), 'by_variation':counts,
            'changed_pairs':sum(row['changed'] for row in counts.values()),
            'status':'counterfactual_research_not_fairness_certification',
            'limitations':['La variation peut modifier un signal légitime; revue humaine nécessaire.',
                           'Aucun attribut sensible n’est inféré.',
                           'Une invariance parfaite sur les paires ne garantit pas une absence de biais indirect.']}


def group_audit(rows: list[dict], *, min_group_size: int = 10) -> dict:
    """Descriptive error rates from independently consented, labeled data.

    rows: group_code, true_support bool, predicted_support bool. Threshold is
    fixed *before* test evaluation. Never return identifying rows or group lists
    with fewer than k cases; labels should be collected separately and lawfully.
    """
    if not 10 <= min_group_size <= 1000 or len(rows) > 1_000_000:
        raise ValueError('INVALID_AUDIT_PARAMETERS')
    by_group = defaultdict(list)
    for row in rows:
        group = row.get('group_code')
        if not isinstance(group,str) or not 1 <= len(group) <= 50:
            raise ValueError('INVALID_GROUP')
        if not isinstance(row.get('true_support'),bool) or not isinstance(row.get('predicted_support'),bool):
            raise ValueError('LABELS_MUST_BE_BOOLEAN')
        by_group[group].append(row)
    groups = {}
    suppressed = 0
    for code, data in sorted(by_group.items()):
        if len(data) < min_group_size:
            suppressed += 1
            continue
        positive = [x for x in data if x['true_support']]
        negative = [x for x in data if not x['true_support']]
        tp = sum(x['predicted_support'] for x in positive)
        fp = sum(x['predicted_support'] for x in negative)
        groups[code] = {'n':len(data), 'false_positive_rate':round(fp/len(negative),4) if negative else None,
                        'true_positive_rate':round(tp/len(positive),4) if positive else None,
                        'false_negative_rate':round((len(positive)-tp)/len(positive),4) if positive else None,
                        'positive_rate':round(sum(x['predicted_support'] for x in data)/len(data),4)}
    def gap(metric):
        vals = [x[metric] for x in groups.values() if x[metric] is not None]
        return round(max(vals)-min(vals),4) if len(vals) >= 2 else None
    return {'total_records':len(rows),'groups_published':len(groups),'groups_suppressed':suppressed,
            'min_group_size':min_group_size,'metrics_by_group':groups,
            'gaps':{key:gap(key) for key in ('false_positive_rate','true_positive_rate','false_negative_rate','positive_rate')},
            'status':'descriptive_research_not_fairness_certification',
            'limitations':['Données de groupes requises légalement et séparées du matching.',
                           'L’absence de labels équilibrés rend certains taux non calculables.',
                           'Les données peu nombreuses ne permettent aucune conclusion causale.']}
