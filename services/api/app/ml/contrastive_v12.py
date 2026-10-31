"""V12 research-only contrastive *passage retrieval* with bounded, offline features.

This is a trainable embedding projection on hashed character n-grams, NOT
fine-tuning BGE-M3. No applicant scores, inferred skills, remote models or
unlabelled negative sampling. Human-annotated positive/hard-negative pairs only.

The fixed-size hash encoder has no fitted vocabulary, so neither its parameters
nor the exported projection encode literal CV phrases or personal tokens.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from app.ml.hybrid_evaluation import QueryLabel, _metrics, read_benchmark
from app.ml.hybrid_retrieval import SourcePassage, _ordered, _dense_scores, bm25_scores, _tfidf_scores
from app.ml.ranking_experiment import read_family_manifest

VERSION = 'contrastive-hashed-passages-v12.0'
INPUT_DIM = 512
OUTPUT_DIM = 48
ENCODER = 'scikit-learn-hashing-char_wb-3_5-l2-v1'
SEED = 12026


def _hashed(texts: Sequence[str]) -> np.ndarray:
    """Stateless, deterministic character features; no training or vocabulary."""
    if len(texts) > 2000 or any(not isinstance(t, str) or len(t) > 5000 for t in texts):
        raise ValueError('INVALID_TEXT_BATCH')
    if not texts:
        return np.empty((0, INPUT_DIM), dtype=np.float32)
    hv = HashingVectorizer(n_features=INPUT_DIM, analyzer='char_wb',
                           ngram_range=(3, 5), lowercase=True,
                           strip_accents='unicode', alternate_sign=False,
                           norm='l2', dtype=np.float32)
    return hv.transform(texts).toarray()


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


@dataclass(frozen=True)
class HashBaseline:
    """A fixed zero-training reference encoder, to detect learned-model regressions."""
    def encode(self, texts: list[str]) -> np.ndarray:
        return _hashed(texts)


@dataclass(frozen=True)
class ContrastiveProjection:
    """A frozen inference object. Model score is cosine, NOT competence confidence."""
    weights: np.ndarray

    def __post_init__(self):
        w = np.asarray(self.weights)
        if (w.shape != (INPUT_DIM, OUTPUT_DIM) or w.dtype.kind not in 'f'
                or not np.isfinite(w).all() or np.max(np.abs(w)) > 100):
            raise ValueError('INVALID_CONTRASTIVE_WEIGHTS')
        immutable = np.array(w, dtype=np.float32, copy=True)
        immutable.setflags(write=False)
        object.__setattr__(self, 'weights', immutable)

    def encode(self, texts: list[str]) -> np.ndarray:
        return _unit(_hashed(texts) @ self.weights)


def _partition(passages: list[SourcePassage], queries: list[QueryLabel],
               manifest: Path) -> tuple[dict[str, list[QueryLabel]], dict]:
    """Frozen family splits plus labelled-document embargo before training."""
    families, assignments = read_family_manifest(manifest, queries)
    parts = {name: [q for q in queries if assignments[families[q.query_id]] == name]
             for name in ('train', 'calibration', 'test')}
    indexed = {p.passage_id: p for p in passages}
    heldout_documents = {indexed[pid].document_id for split in ('calibration', 'test')
                         for q in parts[split]
                         for pid in q.relevant_passage_ids | q.hard_negative_passage_ids}
    retained: list[QueryLabel] = []
    removed = 0
    for q in parts['train']:
        positives = frozenset(pid for pid in q.relevant_passage_ids
                              if indexed[pid].document_id not in heldout_documents)
        negatives = frozenset(pid for pid in q.hard_negative_passage_ids
                              if indexed[pid].document_id not in heldout_documents)
        removed += len(q.relevant_passage_ids | q.hard_negative_passage_ids) - len(positives | negatives)
        if positives and negatives:
            retained.append(replace(q, relevant_passage_ids=positives,
                                    hard_negative_passage_ids=negatives))
    if len(retained) < 3 or any(len(parts[s]) < 2 for s in ('calibration', 'test')):
        raise ValueError('INSUFFICIENT_EMBARGOED_SPLITS')
    parts['train'] = retained
    labelled = {s: {indexed[pid].document_id for q in group for pid in
                   q.relevant_passage_ids | q.hard_negative_passage_ids}
                for s, group in parts.items()}
    overlaps = {f'{a}_{b}': len(labelled[a] & labelled[b])
                for a, b in [('train','calibration'),('train','test'),('calibration','test')]}
    if any(overlaps.values()):
        raise ValueError('DOCUMENT_LABEL_LEAKAGE')
    return parts, {'train_queries_before_embargo':sum(1 for q in queries if assignments[families[q.query_id]] == 'train'),
                   'embargoed_training_judgments': removed,
                   'labelled_document_overlap': overlaps,
                   'train_queries_after_embargo': len(retained),
                   'training_families': len(set(families[q.query_id] for q in retained))}


def _triples(passages: list[SourcePassage], train: list[QueryLabel]):
    lookup = {p.passage_id: p for p in passages}
    triples = [(q.requirement, lookup[pid].text, lookup[nid].text)
               for q in sorted(train, key=lambda x: x.query_id)
               for pid in sorted(q.relevant_passage_ids)
               for nid in sorted(q.hard_negative_passage_ids)]
    if len(triples) < 6:
        raise ValueError('INSUFFICIENT_EXPLICIT_TRIPLES')
    q, p, n = zip(*triples)
    return (_hashed(q), _hashed(p), _hashed(n), len(triples))


def _evaluator(passages: list[SourcePassage], queries: list[QueryLabel],
               encoder) -> dict:
    """Only aggregated numbers; respects per-query organization and document scope."""
    by_language: dict[str, list[dict]] = defaultdict(list)
    for q in queries:
        permitted = [p for p in passages if p.organization_id == q.organization_id
                     and p.document_id in q.authorized_documents]
        if not permitted:
            raise ValueError('EMPTY_AUTHORIZED_EVALUATION_SET')
        ordered = _ordered(_dense_scores(q.requirement,[p.text for p in permitted],encoder),permitted)
        by_language[q.language].append(_metrics(ordered, q, (1,3,5)))
    def summarize(rows):
        if not rows:
            return None
        return {'queries':len(rows), **{key:round(mean(r[key] for r in rows),4)
                for key in ('mrr','hit_at_1','recall_at_3','recall_at_5',
                            'hard_negative_above_first_positive')}}
    return {'all':summarize([row for rows in by_language.values() for row in rows]),
            'by_language':{lang:summarize(rows) for lang, rows in sorted(by_language.items())}}


def train_projection(passages: list[SourcePassage], train: list[QueryLabel],
                     calibration: list[QueryLabel], *, epochs: int = 60,
                     learning_rate: float = 0.025, margin: float = 0.20) -> tuple[ContrastiveProjection, dict]:
    """Train an embedding projection via explicitly supervised triplet margin.

    Validation chooses an epoch; it never updates network weights or vocabulary.
    No test query/label is supplied here. Torch is imported only when training.
    """
    if (type(epochs) is not int or not 10 <= epochs <= 200 or epochs % 10 or
        not 0.0001 <= learning_rate <= 0.1 or not 0.05 <= margin <= 0.8 or
        not math.isfinite(learning_rate) or not math.isfinite(margin)):
        raise ValueError('INVALID_CONTRASTIVE_CONFIG')
    import torch
    import torch.nn.functional as F
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    # Build fixed CPU tensors ONLY from training judgments.
    Q, P, N, count = _triples(passages, train)
    q = torch.from_numpy(Q)
    p = torch.from_numpy(P)
    n = torch.from_numpy(N)
    weight = torch.nn.Parameter(torch.randn(INPUT_DIM, OUTPUT_DIM, generator=torch.Generator().manual_seed(SEED))
                                / math.sqrt(OUTPUT_DIM))
    optimizer = torch.optim.Adam([weight], lr=learning_rate)
    evaluations = []
    with torch.no_grad():
        q0 = F.normalize(q @ weight, dim=1)
        p0 = F.normalize(p @ weight, dim=1)
        n0 = F.normalize(n @ weight, dim=1)
        initial_loss = float(F.relu(margin + (q0*n0).sum(1) - (q0*p0).sum(1)).mean())
    winner = None
    best_key = None
    best_epoch = None
    for epoch in range(epochs + 1):
        if epoch % 10 == 0:
            candidate = ContrastiveProjection(weight.detach().numpy())
            result = _evaluator(passages, calibration, candidate)['all']
            # Choose on calibration only; prefer a smaller false-positive exposure,
            # then fewer epochs when metrics tie.  Test labels NEVER enter.
            key = (result['mrr'], -result['hard_negative_above_first_positive'], -epoch)
            evaluations.append({'epoch':epoch, **result})
            if best_key is None or key > best_key:
                best_key, best_epoch, winner = key, epoch, candidate
        if epoch == epochs:
            break
        optimizer.zero_grad()
        qv = F.normalize(q @ weight, dim=1)
        pv = F.normalize(p @ weight, dim=1)
        nv = F.normalize(n @ weight, dim=1)
        pos = (qv * pv).sum(dim=1)
        neg = (qv * nv).sum(dim=1)
        loss = F.relu(margin + neg - pos).mean()
        loss.backward()
        optimizer.step()
    assert winner is not None
    with torch.no_grad():
        qf = F.normalize(q @ weight, dim=1)
        pf = F.normalize(p @ weight, dim=1)
        nf = F.normalize(n @ weight, dim=1)
        final_loss = float(F.relu(margin + (qf*nf).sum(1) - (qf*pf).sum(1)).mean())
    return winner, {'training_explicit_positive_negative_triples': count,
                    'negative_labels_from_humans_only': True,
                    'optimizer': 'Adam', 'loss': 'cosine_triplet_margin',
                    'epochs_considered': [e['epoch'] for e in evaluations],
                    'selected_epoch_from_calibration':best_epoch,
                    'calibration_trials':evaluations,
                    'seed':SEED,'learning_rate':learning_rate,'margin':margin,
                    'training_loss_initial':round(initial_loss,6),
                    'training_loss_final':round(final_loss,6)}


def run_contrastive_experiment(dataset: Path, manifest: Path, *,
                               output: Path | None = None, artifact: Path | None = None,
                               epochs: int = 60) -> dict:
    passages, queries = read_benchmark(dataset)
    parts, security = _partition(passages,queries,manifest)
    # Train+select on train and calibration ONLY; evaluate heldout test once.
    selected, train_info = train_projection(passages, parts['train'], parts['calibration'], epochs=epochs)
    baseline_calibration = _evaluator(passages,parts['calibration'],HashBaseline())['all']
    selected_calibration = _evaluator(passages,parts['calibration'],selected)['all']
    # A strict guard against falsely claiming a gain from learned vectors.
    # Neither this flag nor any model can trigger deployment/hiring.
    calibration_gain = selected_calibration['mrr'] > baseline_calibration['mrr'] and (        selected_calibration['hard_negative_above_first_positive'] <=
        baseline_calibration['hard_negative_above_first_positive'])
    test = {
        'tfidf_char': _evaluate_lexical(passages,parts['test'],'tfidf'),
        'bm25': _evaluate_lexical(passages,parts['test'],'bm25'),
        'hash_baseline': _evaluator(passages,parts['test'],HashBaseline()),
        'contrastive_hash':_evaluator(passages,parts['test'],selected),
    }
    report = {'research_only':True, 'version':VERSION,
              'encoder':ENCODER,'training':'contrastive_projection_over_hashed_char_ngrams',
              'is_pretrained_transformer':False,
              'no_applicant_scoring_or_automatic_hiring':True,
              'train_queries_original':security['train_queries_before_embargo'],
              'calibration_queries':len(parts['calibration']),
              'test_queries':len(parts['test']),
              'leakage_controls':security,'training':train_info,
              'calibration_hash_baseline':baseline_calibration,
              'calibration_selected_projection':selected_calibration,
              'calibration_strict_gain_over_hash_baseline':bool(calibration_gain),
              'eligible_for_recruitment_inference':False,
              'heldout_test':test,
              'dataset_sha256':sha256(dataset.read_bytes()).hexdigest(),
              'manifest_sha256':sha256(manifest.read_bytes()).hexdigest(),
              'limitations': ('Synthetic passages only. Character hashing is not a pretrained semantic '
                 'model and may fail paraphrases or new domains. Repeated retrieval corpus across '
                 'queries and tiny test set; no person-level split, performance guarantee, '
                 'fairness certification or model deployment. Embedding cosine is not a '
                 'probability or evidence of a skill.')}
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if artifact:
        save_projection(artifact, selected, dataset_sha=report['dataset_sha256'],
                        manifest_sha=report['manifest_sha256'], selected_epoch=train_info['selected_epoch_from_calibration'])
    return report


def _evaluate_lexical(passages, queries, method):
    by_language = defaultdict(list)
    for q in queries:
        permitted = [p for p in passages if p.organization_id==q.organization_id
                     and p.document_id in q.authorized_documents]
        score = (bm25_scores(q.requirement,[p.text for p in permitted]) if method=='bm25'
                 else _tfidf_scores(q.requirement,[p.text for p in permitted]))
        rank = _ordered(score,permitted)
        by_language[q.language].append(_metrics(rank,q,(1,3,5)))
    def aggregate(values):
        return {'queries':len(values), **{key:round(mean(r[key] for r in values),4)
                for key in ('mrr','hit_at_1','recall_at_3','recall_at_5','hard_negative_above_first_positive')}}
    return {'all':aggregate([r for rows in by_language.values() for r in rows]),
            'by_language':{l:aggregate(rows) for l,rows in sorted(by_language.items())}}


def save_projection(path: Path, model: ContrastiveProjection, *,
                    dataset_sha: str, manifest_sha: str, selected_epoch: int):
    """Bounded JSON, no pickle, no fitted vocabulary, no CV text, SHA for corruption only."""
    import re
    if (not all(re.fullmatch('[0-9a-f]{64}', x) for x in (dataset_sha,manifest_sha))
        or type(selected_epoch) is not int or not 0 <= selected_epoch <= 200):
        raise ValueError('INVALID_PROJECTION_METADATA')
    payload = {'version':VERSION,'encoder':ENCODER,'shape':[INPUT_DIM,OUTPUT_DIM],
               'weights':np.round(model.weights,7).tolist(),
               'dataset_sha256':dataset_sha,'manifest_sha256':manifest_sha,
               'selected_epoch':selected_epoch,
               'usage':'offline_research_passage_retrieval_only'}
    canonical = json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    envelope = {'payload':payload, 'integrity_sha256':sha256(canonical.encode('utf-8')).hexdigest()}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(envelope,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')


def load_projection(path: Path) -> ContrastiveProjection:
    if not path.is_file() or not 1000 < path.stat().st_size < 1_500_000:
        raise ValueError('INVALID_PROJECTION_ARTIFACT')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError) as exc:
        raise ValueError('INVALID_PROJECTION_ARTIFACT') from exc
    if type(data) is not dict or set(data) != {'payload','integrity_sha256'}:
        raise ValueError('INVALID_PROJECTION_ARTIFACT')
    payload = data['payload']
    if type(payload) is not dict or set(payload) != {'version','encoder','shape','weights',
                    'dataset_sha256','manifest_sha256','selected_epoch','usage'}:
        raise ValueError('INVALID_PROJECTION_ARTIFACT')
    canonical = json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    if type(data['integrity_sha256']) is not str or sha256(canonical.encode('utf-8')).hexdigest()!=data['integrity_sha256']:
        raise ValueError('PROJECTION_INTEGRITY_MISMATCH')
    if (payload['version'] != VERSION or payload['encoder'] != ENCODER or
        payload['shape'] != [INPUT_DIM,OUTPUT_DIM] or
        payload['usage'] != 'offline_research_passage_retrieval_only'):
        raise ValueError('INCOMPATIBLE_PROJECTION')
    import re
    if (type(payload['selected_epoch']) is not int or not 0 <= payload['selected_epoch'] <= 200 or
        any(type(payload[k]) is not str or re.fullmatch('[a-f0-9]{64}',payload[k]) is None
            for k in ('dataset_sha256','manifest_sha256'))):
        raise ValueError('INVALID_PROJECTION_METADATA')
    weights = payload['weights']
    if (type(weights) is not list or len(weights) != INPUT_DIM or
        any(type(r) is not list or len(r) != OUTPUT_DIM or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in r)
            for r in weights)):
        raise ValueError('INVALID_PROJECTION_WEIGHTS')
    return ContrastiveProjection(np.asarray(weights,dtype=np.float32))
