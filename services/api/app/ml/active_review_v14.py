"""Privacy-preserving, offline ACTIVE ANNOTATION queue for documentary skill evidence.

BM25 and char TF-IDF disagreement only CHOOSES passages for humans to label.
Neither high retrieval rank nor disagreement means a skill is present/absent.
Scope is applied *before* either scorer consumes document text. Candidate lists
contain identifiers, provenance and hashes; never raw applicant passages.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import math
import os
from typing import Sequence

from app.ml.hybrid_evaluation import QueryLabel, validate_benchmark, read_benchmark
from app.ml.hybrid_retrieval import SourcePassage, bm25_scores, _tfidf_scores, _ordered
from app.ml.ranking_experiment import read_family_manifest

VERSION = 'active-annotation-bm25-tfidf-v14.0'


def select_review_items(passages: Sequence[SourcePassage], queries: Sequence[QueryLabel], *,
                        allowed_query_ids: frozenset[str], per_query: int = 3,
                        max_items: int = 100) -> dict:
    """Propose unknown judgments, never leak another tenant's passages to scorers.

    `allowed_query_ids` must come from a frozen split manifest; it cannot be
    implicitly broadened by the current operator or a prediction.
    """
    validate_benchmark(passages, queries)
    qids = {q.query_id for q in queries}
    if (not allowed_query_ids or not allowed_query_ids <= qids or
        isinstance(per_query, bool) or not isinstance(per_query,int) or not 1 <= per_query <= 10 or
        isinstance(max_items,bool) or not isinstance(max_items,int) or not 1 <= max_items <= 500):
        raise ValueError('INVALID_ACTIVE_REVIEW_CONFIG')
    grouped = defaultdict(list)
    for q in sorted(queries, key=lambda q: q.query_id):
        if q.query_id not in allowed_query_ids:
            continue
        permitted = [p for p in passages if p.organization_id == q.organization_id and
                     p.document_id in q.authorized_documents]
        if not permitted:
            raise ValueError('EMPTY_AUTHORIZED_REVIEW_CORPUS')
        texts = [p.text for p in permitted]
        # Both models see only *authorized* source text, never all tenants.
        bm = _ordered(bm25_scores(q.requirement, texts), permitted)
        tf = _ordered(_tfidf_scores(q.requirement, texts), permitted)
        brank, trank = ({pid: i + 1 for i, pid in enumerate(order)} for order in (bm, tf))
        judged = q.relevant_passage_ids | q.hard_negative_passage_ids
        choices = []
        for p in permitted:
            if p.passage_id in judged:
                continue
            # Reciprocal ranks only prioritize human inspection. No probability.
            r1, r2 = brank[p.passage_id], trank[p.passage_id]
            hard_case_priority = 1.0 / min(r1, r2)
            disagreement = abs(1.0 / r1 - 1.0 / r2)
            priority = hard_case_priority + 0.5 * disagreement
            if not math.isfinite(priority):
                raise ValueError('NONFINITE_REVIEW_PRIORITY')
            choices.append((priority, p.passage_id, p, r1, r2))
        choices.sort(key=lambda row: (-row[0], row[1]))
        for priority, _, p, r1, r2 in choices[:per_query]:
            grouped[q.language].append({
                'query_id': q.query_id, 'organization_id': q.organization_id,
                'document_id': p.document_id, 'passage_id': p.passage_id,
                'page_number': p.page_number, 'start_offset': p.start_offset,
                'end_offset': p.end_offset, 'text_sha256': p.text_sha256,
                'source_review_priority': round(priority, 8),
                'bm25_rank': r1, 'tfidf_rank': r2,
                'language': q.language, 'human_label': None,
                'annotation_state': 'two_independent_annotators_required',
            })
    # Alternate languages so the largest language group does not monopolize review.
    items = []
    lang_order = sorted(grouped)
    while len(items) < max_items and any(grouped.values()):
        for lang in lang_order:
            if grouped[lang] and len(items) < max_items:
                items.append(grouped[lang].pop(0))
    return {
        'version': VERSION, 'purpose': 'human_annotation_only',
        'no_auto_labels': True, 'no_recruitment_decisions': True,
        'eligible_for_rh_scoring': False,
        'items': items, 'item_count': len(items),
        'note': 'Ranks are sampling signals, not skill evidence. Review CV pages under existing authorization.',
    }


def write_private_queue(path: Path, payload: dict) -> Path:
    """Create an owner-only artifact, never overwrite review work or print CVs."""
    if payload.get('version') != VERSION or payload.get('no_auto_labels') is not True:
        raise ValueError('INVALID_REVIEW_QUEUE')
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if len(encoded) > 2_000_000:
        raise ValueError('REVIEW_QUEUE_TOO_LARGE')
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as fh:
            fh.write(encoded)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def generate_training_queue(dataset: Path, manifest: Path, *, organization_id: str,
                            per_query: int = 3, max_items: int = 100) -> dict:
    if not organization_id or not isinstance(organization_id, str) or len(organization_id) > 128:
        raise ValueError('ORGANIZATION_SCOPE_REQUIRED')
    passages, queries = read_benchmark(dataset)
    families, split = read_family_manifest(manifest, queries)
    allowed = frozenset(q.query_id for q in queries if q.organization_id == organization_id
                        and split[families[q.query_id]] == 'train')
    output = select_review_items(passages, queries, allowed_query_ids=allowed,
                                 per_query=per_query, max_items=max_items)
    output['dataset_sha256'] = sha256(dataset.read_bytes()).hexdigest()
    output['manifest_sha256'] = sha256(manifest.read_bytes()).hexdigest()
    output['frozen_split'] = 'train'
    output['organization_id'] = organization_id
    return output
