"""Frozen family-held-out learning-to-rank experiment (research only).

Split families are specified BEFORE fitting; only train labels fit model and
only calibration labels pick C. Test labels are consulted just once for metrics.
Metrics contain no raw CV text. Tiny synthetic groups have no hiring validity.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from typing import Sequence

from app.ml.hybrid_evaluation import QueryLabel, _metrics, validate_benchmark
from app.ml.hybrid_retrieval import SourcePassage, _ordered, bm25_scores, _tfidf_scores, retrieve_passages
from app.ml.pairwise_ranker import LinearPassageReranker, train_pairwise, save_ranker

SPLITS = ('train', 'calibration', 'test')


def read_family_manifest(path: Path, queries: Sequence[QueryLabel]) -> tuple[dict[str, str], dict[str, str]]:
    if not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError('INVALID_GROUP_MANIFEST')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or set(obj) != {'families', 'split_by_family'}:
        raise ValueError('INVALID_GROUP_MANIFEST')
    families, splits = obj['families'], obj['split_by_family']
    if not isinstance(families, dict) or not isinstance(splits, dict):
        raise ValueError('INVALID_GROUP_MANIFEST')
    if set(families) != {q.query_id for q in queries} or set(splits) != set(families.values()):
        raise ValueError('INCOMPLETE_GROUP_MANIFEST')
    if not all(isinstance(g, str) and 2 <= len(g) <= 90 for g in families.values()):
        raise ValueError('INVALID_GROUP_NAMES')
    if not set(splits.values()) == set(SPLITS):
        raise ValueError('INVALID_THREE_WAY_SPLIT')
    return families, splits


def _ordering(q: QueryLabel, passages: list[SourcePassage], model: LinearPassageReranker | None) -> dict[str, list[str]]:
    permitted = [p for p in passages if p.organization_id == q.organization_id
                 and p.document_id in q.authorized_documents]
    texts = [p.text for p in permitted]
    if not permitted:
        raise ValueError('EMPTY_AUTHORIZED_CORPUS')
    rrf = retrieve_passages(q.requirement, permitted, organization_id=q.organization_id,
                            authorized_documents=q.authorized_documents,
                            top_k=len(permitted), rerank_top_n=min(100, len(permitted)))
    ranks = {'bm25': _ordered(bm25_scores(q.requirement, texts), permitted),
             'tfidf_char': _ordered(_tfidf_scores(q.requirement, texts), permitted),
             'rrf_lexical': [r['passage_id'] for r in rrf['items']]}
    if model is not None:
        prediction = retrieve_passages(q.requirement, permitted,
                         organization_id=q.organization_id,
                         authorized_documents=q.authorized_documents,
                         reranker=model, top_k=len(permitted),
                         rerank_top_n=min(100, len(permitted)))
        ranks['learned_pairwise'] = [r['passage_id'] for r in prediction['items']]
    return ranks


def evaluate_rankings(passages: list[SourcePassage], queries: list[QueryLabel],
                      model: LinearPassageReranker | None = None) -> dict:
    validate_benchmark(passages, queries)
    summary: dict[str, list[tuple[str,dict]]] = defaultdict(list)
    for q in queries:
        for name, ids in _ordering(q, passages, model).items():
            summary[name].append((q.language, _metrics(ids, q, (1,3,5))))
    output = {}
    for name, entries in summary.items():
        def summarize(rows: list[dict]) -> dict | None:
            if not rows: return None
            fields = ('mrr','hit_at_1','recall_at_3','recall_at_5',
                      'hard_negative_above_first_positive','hard_negative_at_1')
            return {'queries':len(rows), **{key:round(mean(x[key] for x in rows),4) for key in fields}}
        output[name] = {'all':summarize([r for _,r in entries]),
                         'by_language':{lang:summarize([r for l,r in entries if l==lang])
                                        for lang in ('fr','en') if any(l==lang for l,_ in entries)}}
    return output


def run_grouped_experiment(dataset: Path, manifest: Path, *, output: Path | None = None,
                           artifact: Path | None = None, candidates: tuple[float,...] = (.05,.25,1.0,4.0)) -> dict:
    from app.ml.hybrid_evaluation import read_benchmark
    passages, queries = read_benchmark(dataset)
    families, splits = read_family_manifest(manifest, queries)
    groups = {split:[q for q in queries if splits[families[q.query_id]] == split]
              for split in SPLITS}
    if any(len(groups[s]) < 2 for s in SPLITS):
        raise ValueError('INSUFFICIENT_GROUPED_QUERIES')
    if (not candidates or len(candidates)!=len(set(candidates)) or
        any(not 0.01 <= c <= 100 for c in candidates)):
        raise ValueError('INVALID_CANDIDATE_GRID')
    # Embargo *labelled passages/documents* from calibration/test when fitting.
    # This avoids training directly on a passage used to judge the held-out sets.
    # Only use document identifiers to enforce this constraint; never use their labels.
    indexed = {p.passage_id: p for p in passages}
    heldout_docs = {indexed[pid].document_id for part in ('calibration', 'test')
                    for q in groups[part]
                    for pid in (q.relevant_passage_ids | q.hard_negative_passage_ids)}
    embargoed = []
    dropped = 0
    for q in groups['train']:
        positives = frozenset(pid for pid in q.relevant_passage_ids
                              if indexed[pid].document_id not in heldout_docs)
        negatives = frozenset(pid for pid in q.hard_negative_passage_ids
                              if indexed[pid].document_id not in heldout_docs)
        dropped += len(q.relevant_passage_ids | q.hard_negative_passage_ids) - len(positives | negatives)
        if positives and negatives:
            embargoed.append(replace(q, relevant_passage_ids=positives,
                                    hard_negative_passage_ids=negatives))
    if len(embargoed) < 3:
        raise ValueError('INSUFFICIENT_AFTER_HELDOUT_DOCUMENT_EMBARGO')
    # Tuning only considers calibration labels; never inspect test metrics before freezing C.
    validation_trials = []
    for c in sorted(candidates):
        candidate, info = train_pairwise(passages, embargoed, regularization=c)
        metrics = evaluate_rankings(passages, groups['calibration'], candidate)
        result = metrics['learned_pairwise']['all']
        validation_trials.append((result['mrr'], -result['hard_negative_above_first_positive'],
                                  -c, c, candidate, info))
    chosen = max(validation_trials, key=lambda row:row[:3])
    best, info = chosen[4], chosen[5]
    test_metrics = evaluate_rankings(passages, groups['test'], best)
    calibr_metrics = evaluate_rankings(passages, groups['calibration'], best)
    # Counts only: documents in the shared retrieval corpus can still be present
    # in other splits. Future real-world validation MUST split by CV/person too.
    evaluated_groups = {**groups, 'train':embargoed}
    labelled_docs = {s:{indexed[pid].document_id for q in evaluated_groups[s] for pid in
                        q.relevant_passage_ids | q.hard_negative_passage_ids} for s in SPLITS}
    overlaps = {f'{a}_{b}':len(labelled_docs[a] & labelled_docs[b])
                for i,a in enumerate(SPLITS) for b in SPLITS[i+1:]}
    report = {
       'research_only':True, 'source':'synthetic_or_explicitly_licensed_expert_annotations',
       'algorithm':'regularized_logistic_pairwise_preference',
       'threshold_or_competence_probability':None,
       'train_queries':len(groups['train']), 'calibration_queries':len(groups['calibration']),
       'test_queries':len(groups['test']),
       'family_counts':{s:len({families[q.query_id] for q in groups[s]}) for s in SPLITS},
       'selected_regularization_c':chosen[3], 'train_details':info,
       'embargoed_training_judgments': dropped,
       'train_queries_retained_after_document_embargo':len(embargoed),
       'calibration_candidates':[{'C':c,'mrr':mrr,'hard_negative_rate':-neg}
                                 for mrr,neg,_,c,_,_ in validation_trials],
       'calibration_results':calibr_metrics,
       'heldout_test_results':test_metrics,
       'judged_document_overlap_between_splits':overlaps,
       'dataset_sha256':sha256(dataset.read_bytes()).hexdigest(),
       'manifest_sha256':sha256(manifest.read_bytes()).hexdigest(),
       'limitations':('Only 3 synthetic held-out queries in this fixture; training labels are document-embargoed, '
           'but the retrieval corpus is shared and can contain the same passage in all queries. '
           'This is not a person-held-out real-CV evaluation. '
           'No actual transformer model, fairness or real-CV benchmarking, no hiring interpretation. '
           'Unknown relevance judgments remain unknown; measured metrics may be incomplete.')}
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if artifact is not None:
        save_ranker(artifact,best,training_sha256=report['dataset_sha256'],
                    split_sha256=report['manifest_sha256'],training_info=info)
    return report


def evaluate_adversarial_challenges(path: Path, model: LinearPassageReranker) -> dict:
    """Diagnostic against fictional adversarial alternatives; not a valid hiring metric.

    Only compares the order of two passages. Does not call the matching engine,
    make decisions, generate competence labels or export raw text.
    """
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError('INVALID_CHALLENGE_FILE')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or set(obj) != {'dataset_type','cases'} or \
       obj['dataset_type'] != 'handcrafted_synthetic_evidence_vs_trap' or \
       not isinstance(obj['cases'], list) or not 2 <= len(obj['cases']) <= 1000:
        raise ValueError('INVALID_CHALLENGE_FORMAT')
    from app.ml.hybrid_retrieval import _tfidf_scores
    counters = defaultdict(lambda: {'wins':0,'losses':0,'ties':0})
    seen = set()
    for case in obj['cases']:
        if not isinstance(case,dict) or set(case) != {'id','language','trap','requirement','positive','negative'} or \
           case['language'] not in ('fr','en') or case['trap'] not in ('negation','learning','job_ad','conditional') or \
           not isinstance(case['id'],str) or case['id'] in seen:
            raise ValueError('INVALID_CHALLENGE_CASE')
        seen.add(case['id'])
        pair_scores = model.predict([(case['requirement'],case['positive']),
                                     (case['requirement'],case['negative'])])
        tfidf_scores = _tfidf_scores(case['requirement'], [case['positive'],case['negative']])
        for method, scores in (('learned_pairwise',pair_scores),('tfidf_char',tfidf_scores)):
            delta=scores[0]-scores[1]
            outcome = 'ties' if abs(delta)<1e-10 else 'wins' if delta > 0 else 'losses'
            for dimension in ('all',case['language'],'trap_'+case['trap']):
                counters[f'{method}/{dimension}'][outcome]+=1
    return {'dataset_sha256':sha256(path.read_bytes()).hexdigest(),
       'synthetic_pairs':len(seen),
       'method_group_diagnostics':dict(sorted(counters.items())),
       'disclaimer':'Synthetic hand-crafted pair order only; no calibrated probability, no skill confirmation, no deployment validity.'}
