"""Transparent coverage of source-anchored *mentions*, never candidate suitability.

A criterion requiring manual evaluation is **not** scored as zero. A complete /100
score is deliberately unavailable until all configured criteria are machine-evaluable.
A separately labelled diagnostic describes coverage of the evaluable subset only.
"""
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

ALGORITHM_VERSION = 'documented-coverage-2.0.0'
DEFAULT_WEIGHTS = {'essential': 60, 'desirable': 20, 'experience': 10, 'projects_training': 10}
GROUPS = tuple(DEFAULT_WEIGHTS)
UNASSESSED = frozenset(('manual_review_required', 'needs_review', 'awaiting_documents'))


def group_of(req: dict) -> str:
    if req['category'] == 'experience':
        return 'experience'
    if req['category'] in ('qualification', 'certification', 'other', 'language'):
        return 'projects_training'
    return 'essential' if req['required'] else 'desirable'


def stable_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CriterionScore:
    requirement: dict
    group: str
    state: str
    note_code: str
    contribution: Decimal
    evidence: dict | None


@dataclass(frozen=True)
class MatchScore:
    score: Decimal | None
    state: str
    criteria: list[CriterionScore]
    group_coverage: dict
    fingerprint: str


def calculate(requirements: list[dict], weights: dict[str, int],
              evidence_by_skill: dict[str, list[dict]], mapped_skills: dict[str, str | None],
              *, documents_ready: bool, document_fingerprint: str) -> MatchScore:
    """Calculate *observed* documentary coverage with an explicit unassessed scope.

    Similarity suggestions and unconfirmed evidence never count as observed mentions.
    If any required criterion is not machine-assessable, return `score=None` rather
    than a misleading partial /100; offer an independently labelled diagnostic.
    """
    if (set(weights) != set(GROUPS) or
            any(type(value) is not int or value < 0 for value in weights.values()) or
            sum(weights.values()) != 100):
        raise ValueError('Configuration de pondération invalide')
    grouped = {g: [r for r in requirements if group_of(r) == g] for g in GROUPS}
    active = [g for g in GROUPS if grouped[g]]
    active_weight_total = sum(weights[g] for g in active)
    if not active or active_weight_total == 0:
        raise ValueError('Aucun critère pondérable')
    for group in active:
        if any(type(r['weight']) is not int or r['weight'] <= 0 for r in grouped[group]):
            raise ValueError('Poids de critère invalide')

    effective = {g: Decimal(100 * weights[g]) / Decimal(active_weight_total) for g in active}
    entries = []
    measured_groups = {}
    for group in active:
        assessed = 0
        documented = 0
        denominator = sum(r['weight'] for r in grouped[group])
        for req in grouped[group]:
            skill_id = mapped_skills.get(req['id'])
            candidates = evidence_by_skill.get(skill_id, []) if skill_id else []
            valid = sorted((e for e in candidates if e['status'] in ('mentioned', 'confirmed') and e['source_valid']),
                           key=lambda e: (e['document_id'], e['page_number'], e['start_offset'], e['id']))
            uncertain = any(e['status'] == 'needs_review' for e in candidates)
            if not documents_ready:
                state, note, matched = 'awaiting_documents', 'NLP_NOT_COMPLETE', None
            elif req['category'] != 'skill':
                state, note, matched = 'manual_review_required', 'NON_SKILL_NOT_AUTOMATED', None
            elif skill_id is None:
                state, note, matched = 'manual_review_required', 'NO_VALIDATED_SKILL_MAPPING', None
            elif valid:
                state, note, matched = 'documented_mention', 'EXACT_SOURCE_MENTION', valid[0]
            elif uncertain:
                state, note, matched = 'needs_review', 'AMBIGUOUS_MENTION', None
            else:
                state, note, matched = 'not_documented', 'NO_MATCHING_DOCUMENT_MENTION', None
            if state not in UNASSESSED:
                assessed += req['weight']
                if matched is not None:
                    documented += req['weight']
            entries.append((req, group, state, note, matched, denominator))
        measured_groups[group] = (assessed, documented, denominator)

    assessable_scope = sum((effective[g] * Decimal(measured_groups[g][0]) /
                            Decimal(measured_groups[g][2]) for g in active), Decimal('0'))
    matched_scope = sum((effective[g] * Decimal(measured_groups[g][1]) /
                         Decimal(measured_groups[g][2]) for g in active), Decimal('0'))
    diagnostic = ((Decimal(100) * matched_scope / assessable_scope).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP) if assessable_scope else None)
    complete = (documents_ready and assessable_scope == 100 and
                not any(state in UNASSESSED for _, _, state, _, _, _ in entries))
    result = []
    coverage: dict = {}
    for req, group, state, note, matched, denominator in entries:
        # Contributions are diagnostic only if score=None; callers MUST display scope.
        contribution = ((Decimal(100) * effective[group] * Decimal(req['weight']) /
                         Decimal(denominator) / assessable_scope) if matched and assessable_scope
                        else Decimal('0'))
        result.append(CriterionScore(req, group, state, note, contribution, matched))
    for group in active:
        assessed, documented, total = measured_groups[group]
        coverage[group] = {
            'weight_percent': float(effective[group].quantize(Decimal('0.01'))),
            'documented_weight': documented,
            'assessed_weight': assessed,
            'unassessed_weight': total - assessed,
            'total_criteria_weight': total,
            'coverage': float((Decimal(documented)/Decimal(assessed)).quantize(Decimal('0.0001')))
            if assessed else None,
        }
    coverage['summary'] = {
        'assessable_weight_percent': float(assessable_scope.quantize(Decimal('0.01'))),
        'unassessed_weight_percent': float((Decimal(100) - assessable_scope).quantize(Decimal('0.01'))),
        'evaluable_subset_coverage': float(diagnostic) if diagnostic is not None else None,
        'complete': complete,
        'caution': 'La couverture du sous-ensemble évalué ne reflète pas les critères non évalués.',
    }
    if not documents_ready:
        score, state = None, 'awaiting_documents'
    elif not complete:
        score, state = None, 'partial_review_required'
    else:
        score, state = diagnostic, 'documentary_coverage'
    return MatchScore(score, state, result, coverage, stable_hash({
        'documents': document_fingerprint, 'requirements': requirements, 'weights': weights,
        'mapped': mapped_skills, 'evidence': evidence_by_skill, 'algorithm': ALGORITHM_VERSION
    }))
