"""Phase 10 offline experiments: retrieval metrics over expert-labelled source passages.

No applicant-level ranking, demographic inference, external API or raw CV export.
The dataset must already have been screened for proper processing permission.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import random
from statistics import mean
from typing import Sequence

from app.ml.hybrid_retrieval import (SourcePassage, bm25_scores, _tfidf_scores,
             _dense_scores, _ordered, retrieve_passages)


@dataclass(frozen=True)
class QueryLabel:
    query_id: str
    language: str
    requirement: str
    organization_id: str
    authorized_documents: frozenset[str]
    relevant_passage_ids: frozenset[str]
    hard_negative_passage_ids: frozenset[str]


def read_benchmark(path: Path) -> tuple[list[SourcePassage], list[QueryLabel]]:
    if not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError('INVALID_BENCHMARK_FILE')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload,dict) or not isinstance(payload.get('passages'),list) or not isinstance(payload.get('queries'),list):
        raise ValueError('INVALID_BENCHMARK_FORMAT')
    try:
        passages = [SourcePassage(p['id'],p['organization_id'],p['document_id'],
                     p['page_number'],p['start_offset'],p['text']) for p in payload['passages']]
        queries = [QueryLabel(q['id'],q['language'],q['requirement'],q['organization_id'],
                    frozenset(q['authorized_documents']),frozenset(q['relevant_passage_ids']),
                    frozenset(q.get('hard_negative_passage_ids',[]))) for q in payload['queries']]
    except (TypeError,ValueError,KeyError) as exc:
        raise ValueError('INVALID_BENCHMARK_FORMAT') from exc
    validate_benchmark(passages,queries)
    return passages,queries


def validate_benchmark(passages: Sequence[SourcePassage], queries: Sequence[QueryLabel]) -> None:
    if not passages or not queries or len(passages)>10000 or len(queries)>2000:
        raise ValueError('INVALID_BENCHMARK_SIZE')
    ids = {p.passage_id:p for p in passages}
    if len(ids)!=len(passages) or len({q.query_id for q in queries})!=len(queries):
        raise ValueError('DUPLICATE_EVALUATION_ID')
    if any(not p.passage_id or not p.text.strip() or not p.organization_id or
           not p.document_id or p.start_offset<0 or p.page_number<1 or
           len(p.text)>5000 for p in passages):
        raise ValueError('INVALID_BENCHMARK_PASSAGE')
    for q in queries:
        allowed={p.passage_id for p in passages if p.organization_id==q.organization_id
                 and p.document_id in q.authorized_documents}
        if (q.language not in ('fr','en') or not 2<=len(q.requirement.strip())<=500 or
            not q.query_id or not q.organization_id or not q.authorized_documents or
            not q.relevant_passage_ids or not q.relevant_passage_ids <= allowed or
            not q.hard_negative_passage_ids <= allowed or
            q.relevant_passage_ids & q.hard_negative_passage_ids):
            raise ValueError('INVALID_BENCHMARK_GROUND_TRUTH')


def _metrics(rank: list[str], q: QueryLabel, k_values: tuple[int,...]) -> dict:
    first = next((i for i,identifier in enumerate(rank,1) if identifier in q.relevant_passage_ids),None)
    result={'mrr': 1/first if first is not None else 0.0}
    for k in k_values:
        selected=set(rank[:k]); hits=len(selected & q.relevant_passage_ids)
        result[f'recall_at_{k}']=hits/len(q.relevant_passage_ids)
        result[f'precision_at_{k}']=hits/k
        result[f'hit_at_{k}']=int(hits>0)
        result[f'hard_negative_at_{k}']=len(selected & q.hard_negative_passage_ids)
        dcg=sum(1/__import__('math').log2(i+2) for i,pid in enumerate(rank[:k]) if pid in q.relevant_passage_ids)
        ideal=sum(1/__import__('math').log2(i+2) for i in range(min(k,len(q.relevant_passage_ids))))
        result[f'ndcg_at_{k}']=dcg/ideal if ideal else 0.0
    # Human-facing diagnostic; a hard negative outranking ALL known positives.
    first_positive=min((rank.index(pid) for pid in q.relevant_passage_ids if pid in rank),default=len(rank))
    first_hard_negative=min((rank.index(pid) for pid in q.hard_negative_passage_ids if pid in rank),default=len(rank))
    result['hard_negative_above_first_positive']=int(first_hard_negative<first_positive)
    return result


def _aggregate(metrics: list[dict]) -> dict | None:
    if not metrics: return None
    return {'queries':len(metrics),**{key:round(mean(row[key] for row in metrics),4)
            for key in metrics[0]}}


def _bootstrap_hit_ci(records: list[dict], key: str, *, reps: int = 400,
                      seed: int = 2026) -> list[float] | None:
    # Query-level resampling; no CI for empty or only-one query sets.
    if len(records)<2:return None
    rng=random.Random(seed); n=len(records)
    samples=sorted(mean(records[rng.randrange(n)][key] for _ in range(n)) for _ in range(reps))
    return [round(samples[int(.025*reps)],4),round(samples[min(reps-1,int(.975*reps))],4)]


def evaluate_hybrid(passages: list[SourcePassage], queries: list[QueryLabel], *,
                    embedder=None, reranker=None, k_values: tuple[int,...]=(1,3,5),
                    max_k: int=10) -> dict:
    validate_benchmark(passages,queries)
    if (not k_values or len(set(k_values))!=len(k_values) or
        any(not 1<=k<=max_k for k in k_values) or
        not 1 <= max_k <= 100 or reranker is not None and embedder is None):
        raise ValueError('INVALID_EVALUATION_CONFIG')
    all_records: dict[str,list[tuple[str,dict]]] = defaultdict(list)
    for query in queries:
        permitted=[p for p in passages if p.organization_id==query.organization_id
                   and p.document_id in query.authorized_documents]
        texts=[p.text for p in permitted]
        bm25=_ordered(bm25_scores(query.requirement,texts),permitted)
        tfidf=_ordered(_tfidf_scores(query.requirement,texts),permitted)
        variants={'bm25':bm25,'tfidf_char':tfidf}
        if embedder is not None:
            variants['dense'] = _ordered(_dense_scores(query.requirement,texts,embedder),permitted)
        # Ensure each variant is compared against the same authorized corpus.
        hybrid=retrieve_passages(query.requirement,permitted,
                  organization_id=query.organization_id,
                  authorized_documents=query.authorized_documents,
                  embedder=embedder,reranker=None,top_k=min(max_k,len(permitted)),
                  rerank_top_n=min(100,max_k))
        variants['hybrid_rrf']=[x['passage_id'] for x in hybrid['items']]
        if reranker is not None:
            reranked=retrieve_passages(query.requirement,permitted,
                  organization_id=query.organization_id,
                  authorized_documents=query.authorized_documents,
                  embedder=embedder,reranker=reranker,
                  top_k=min(max_k,len(permitted)),rerank_top_n=min(100,max(max_k,20)))
            variants['hybrid_crossencoder']=[x['passage_id'] for x in reranked['items']]
        for name,ordering in variants.items():
            all_records[name].append((query.language,_metrics(ordering,query,k_values)))
    result={}
    for name, records in all_records.items():
        all_rows=[m for _,m in records]
        result[name]={'all':_aggregate(all_rows),
            'by_language':{lang:_aggregate([m for l,m in records if l==lang])
                           for lang in ('fr','en') if any(l==lang for l,_ in records)},
            'hit_at_1_bootstrap95':_bootstrap_hit_ci(all_rows,'hit_at_1')}
    return {'dataset_type':'synthetic_or_explicitly_licensed_annotated_passages',
            'total_queries':len(queries),'total_passages':len(passages),
            'k_values':list(k_values),'methods':result,
            'warning':('Research-only. Hard-negative exposure is a safety diagnostic; '
                       'none of these retrieval metrics establishes competence, '
                       'fairness, calibrated probability or hiring validity. '
                       'Bootstrap CIs are unstable on small datasets.')}


def suggest_difficult_annotations(passages: list[SourcePassage],
                                  queries: list[QueryLabel], *, limit_per_query:int=2) -> list[dict]:
    """Suggest ambiguous passages; NEVER assign them negative labels."""
    if not 1<=limit_per_query<=10: raise ValueError('INVALID_ANNOTATION_LIMIT')
    validate_benchmark(passages,queries)
    output=[]
    for query in queries:
        search=retrieve_passages(query.requirement,passages,
                     organization_id=query.organization_id,
                     authorized_documents=query.authorized_documents,
                     top_k=min(100,len(passages)))
        used=0
        for item in search['items']:
            if item['passage_id'] not in query.relevant_passage_ids:
                output.append({'query_id':query.query_id,'passage_id':item['passage_id'],
                    'suggested_label':None,'status':'requires_two_independent_annotators'})
                used+=1
                if used >= limit_per_query:break
    return output
