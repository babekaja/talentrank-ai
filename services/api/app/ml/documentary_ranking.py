"""Classement pondéré sur les mêmes critères documentaires pour tous les CV."""
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.ml.matching import group_of
from app.models import Application, Candidate, MatchingResult, MatchingCriterionResult

ASSESSED = frozenset(('documented_mention', 'not_documented'))
READY = frozenset(('documentary_coverage', 'partial_review_required'))


def ranked_results(db, run):
    # Le run est autorisé par l'appelant ; les jointures répètent son organisation.
    rows = db.execute(select(MatchingResult, Candidate.reference, Candidate.full_name)
        .join(Application, (Application.id == MatchingResult.application_id) &
              (Application.organization_id == run.organization_id) &
              (Application.campaign_id == run.campaign_id))
        .join(Candidate, (Candidate.id == MatchingResult.candidate_id) &
              (Candidate.id == Application.candidate_id) &
              (Candidate.organization_id == run.organization_id))
        .where(MatchingResult.run_id == run.id)).all()
    eligible = {result.id for result, _, _ in rows if result.state in READY}
    requirements = run.requirements_snapshot or []
    weights = run.weights_snapshot or {}
    group_totals = {}
    for req in requirements:
        group = group_of(req)
        group_totals[group] = group_totals.get(group, 0) + req['weight']
    active_total = sum(weights.get(group, 0) for group in group_totals)
    criterion_weights = {}
    if active_total:
        for req in requirements:
            group = group_of(req)
            if req['category'] == 'skill' and (run.skill_mapping_snapshot or {}).get(req['id']):
                weight = (Decimal(100) * Decimal(weights.get(group, 0)) * Decimal(req['weight']) /
                          Decimal(active_total) / Decimal(group_totals[group]))
                if weight > 0:
                    criterion_weights[req['id']] = weight
    states = {result_id: {} for result_id in eligible}
    criteria = db.execute(select(MatchingCriterionResult.result_id,
        MatchingCriterionResult.requirement_id, MatchingCriterionResult.state)
        .join(MatchingResult, MatchingResult.id == MatchingCriterionResult.result_id)
        .where(MatchingResult.run_id == run.id)).all()
    for result_id, requirement_id, state in criteria:
        if result_id in states:
            states[result_id][requirement_id] = state
    common = set(criterion_weights) if eligible else set()
    for criteria_states in states.values():
        common.intersection_update(key for key, state in criteria_states.items() if state in ASSESSED)
    scope = sum((criterion_weights[key] for key in common), Decimal(0))
    scores = {}
    if scope:
        for result_id, criteria_states in states.items():
            documented = sum((criterion_weights[key] for key in common
                              if criteria_states[key] == 'documented_mention'), Decimal(0))
            scores[result_id] = (documented * Decimal(100) / scope).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
    ordered = sorted(rows, key=lambda row: (
        row[0].id not in scores, -scores.get(row[0].id, Decimal(0)), row[1], row[0].application_id))
    items = []
    previous = None
    rank = None
    for position, (result, reference, name) in enumerate(ordered, start=1):
        score = scores.get(result.id)
        if score is not None and score != previous:
            rank = position
        previous = score
        items.append((result, {
            'rank': rank if score is not None else None,
            'matching_percentage': float(score) if score is not None else None,
            'ranking_scope_percent': float(scope.quantize(Decimal('0.01'))),
            'candidate_reference': reference, 'candidate_name': name,
        }))
    summary = {
        'assessed_weight_percent': float(scope.quantize(Decimal('0.01'))),
        'criteria_count': len(common), 'ranked_count': len(scores),
        'unranked_count': len(rows) - len(scores), 'provisional': run.status != 'completed',
        'note': 'Classement par correspondance documentaire pondérée décroissante sur les mêmes critères évalués. Les scores égaux partagent le même rang.',
    }
    return items, summary
