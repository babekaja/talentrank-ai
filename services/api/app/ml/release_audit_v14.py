"""Independent, fail-closed *research* readiness audit of local evidence retrieval.

No results of this module may be used to select, reject or evaluate applicants.
Even passing technical checks NEVER authorizes a hiring model: privacy, bias,
regulatory and domain expert reviews are additional independent requirements.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
from statistics import mean
import json
import os
import random

from app.ml.hybrid_evaluation import _metrics, read_benchmark
from app.ml.hybrid_retrieval import _ordered, _tfidf_scores, bm25_scores, _dense_scores
from app.ml.neural_finetune_v13 import prepare_experiment
from app.ml.ranking_experiment import read_family_manifest

VERSION = 'research-readiness-audit-v14.0'
POLICY = {
    'min_test_queries': 200,
    'min_queries_per_language': 50,
    'min_test_skill_families': 8,
    'min_test_tenants': 2,
    'min_test_hit_at_1': 0.70,
    'max_hard_negative_above_first_positive': 0.10,
    'max_language_hit_at_1_gap': 0.10,
    'min_bootstrap_lower95_mrr_delta_vs_tfidf': -0.02,
}


def _paired_bootstrap_delta(candidate: list[float], baseline: list[float],
                            *, seed: int = 14026, reps: int = 1200) -> list[float]:
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError('INVALID_PAIRED_METRICS')
    differences = [a - b for a, b in zip(candidate, baseline)]
    rng = random.Random(seed)
    n = len(differences)
    samples = sorted(mean(differences[rng.randrange(n)] for _ in range(n)) for _ in range(reps))
    return [round(samples[int(.025 * reps)], 5), round(samples[int(.975 * reps)], 5)]


def audit_retrieval_model(dataset: Path, manifest: Path, *, encoder=None) -> dict:
    """Recompute metrics from frozen labels rather than trusting supplied JSON.

    With no encoder, audit the lexical baseline but reject model certification.
    Validation/train labels do not enter metric selection for the test split.
    All texts are filtered by authorization *before* calling the embedder.
    """
    passages, parts, triplets, embargo = prepare_experiment(dataset, manifest)
    families, assignment = read_family_manifest(manifest, read_benchmark(dataset)[1])
    test = sorted(parts['test'], key=lambda q: q.query_id)
    detail = []
    for q in test:
        permitted = [p for p in passages if p.organization_id == q.organization_id and
                     p.document_id in q.authorized_documents]
        if not permitted:
            raise ValueError('EMPTY_AUTHORIZED_TEST_CORPUS')
        txt = [p.text for p in permitted]
        lexical = _ordered(_tfidf_scores(q.requirement, txt), permitted)
        candidate = _ordered(_dense_scores(q.requirement, txt, encoder), permitted) if encoder else lexical
        base = _metrics(lexical, q, (1,3,5))
        pred = _metrics(candidate, q, (1,3,5))
        detail.append((q, pred, base))
    languages = Counter(q.language for q, _, _ in detail)
    families_count = len({families[q.query_id] for q, _, _ in detail})
    tenants = len({q.organization_id for q, _, _ in detail})
    hit = mean(row['hit_at_1'] for _, row, _ in detail)
    bad = mean(row['hard_negative_above_first_positive'] for _, row, _ in detail)
    per_lang = {lang: {'n': languages[lang],
                       'hit_at_1': round(mean(r['hit_at_1'] for q, r, _ in detail if q.language == lang), 5)}
                for lang in sorted(languages)}
    gap = abs(per_lang['fr']['hit_at_1'] - per_lang['en']['hit_at_1']) if set(per_lang) == {'fr','en'} else None
    ci = _paired_bootstrap_delta([p['mrr'] for _,p,_ in detail],
                                 [b['mrr'] for _,_,b in detail])
    checks = {
        'candidate_encoder_was_executed': encoder is not None,
        'test_sample_size': len(detail) >= POLICY['min_test_queries'],
        'both_languages_have_enough_queries': all(languages[l] >= POLICY['min_queries_per_language'] for l in ('fr','en')),
        'diverse_skill_families': families_count >= POLICY['min_test_skill_families'],
        'more_than_one_authorized_organization': tenants >= POLICY['min_test_tenants'],
        'hit_at_1_target': hit >= POLICY['min_test_hit_at_1'],
        'hard_negative_exposure_target': bad <= POLICY['max_hard_negative_above_first_positive'],
        'language_gap_target': gap is not None and gap <= POLICY['max_language_hit_at_1_gap'],
        'paired_bootstrap_no_material_regression': ci[0] >= POLICY['min_bootstrap_lower95_mrr_delta_vs_tfidf'],
        'annotated_document_embargo_valid': not any(embargo['labelled_document_overlap'].values()),
    }
    return {
        'version': VERSION, 'research_only': True,
        'eligible_for_recruitment_inference': False,
        'automatic_promotion': False,
        'research_metric_gate_passed': all(checks.values()),
        'checks': checks, 'policy': POLICY,
        'metrics': {'test_queries': len(detail), 'languages': per_lang,
                    'skill_families': families_count, 'organizations': tenants,
                    'candidate_hit_at_1': round(hit,5),
                    'hard_negative_above_first_positive': round(bad,5),
                    'language_hit_at_1_gap': None if gap is None else round(gap,5),
                    'paired_bootstrap_mrr_delta_95': ci,
                    'baseline_tfidf_mrr': round(mean(b['mrr'] for _,_,b in detail),5),
                    'candidate_mrr': round(mean(p['mrr'] for _,p,_ in detail),5)},
        'data_integrity': {'dataset_sha256': sha256(dataset.read_bytes()).hexdigest(),
                           'manifest_sha256': sha256(manifest.read_bytes()).hexdigest(),
                           'explicit_training_triplets': len(triplets)},
        'unresolved_requirements': [
            'Expert-labelled licensed real CV passages with applicant-disjoint heldout tests',
            'External fairness/privacy/security review and independent evaluation',
            'True MySQL/Redis/MinIO/Qdrant/Angular deployment integration checks',
            'Explicit human authorization; no automatic job decisions'],
        'disclaimer': 'Research metrics are NOT calibrated skill probabilities or hiring suitability.',
    }


def write_audit(path: Path, result: dict) -> None:
    if result.get('version') != VERSION or result.get('automatic_promotion') is not False:
        raise ValueError('INVALID_RELEASE_AUDIT')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation and 0600 from the outset, never transient world readable.
    encoded = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(encoded)
    except Exception:
        path.unlink(missing_ok=True)
        raise
