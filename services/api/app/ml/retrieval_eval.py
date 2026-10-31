"""Offline lexical retrieval baseline for SOURCE PASSAGES, not people.

A controlled comparison point for later multilingual BGE-M3 retrieval experiments.
Relevance labels must be supplied by experts; zero labels => no metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class RetrievalCase:
    query_id: str
    language: str
    requirement: str
    relevant_passage_ids: frozenset[str]


def rank_passages(query: str, passages: list[tuple[str,str]], limit: int = 10) -> list[dict]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    if not query.strip() or not passages or not 1 <= limit <= 100:
        raise ValueError('INVALID_RETRIEVAL_INPUT')
    identifiers = [pid for pid,_ in passages]
    if len(set(identifiers)) != len(identifiers) or any(not pid or not t.strip() for pid,t in passages):
        raise ValueError('INVALID_PASSAGE_IDS')
    vectorizer = TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),
                   strip_accents='unicode',sublinear_tf=True)
    vectors = vectorizer.fit_transform([query]+[passage for _,passage in passages])
    similarities = cosine_similarity(vectors[0],vectors[1:]).ravel()
    ranked = sorted(zip(identifiers, similarities), key=lambda x:(-x[1],x[0]))[:limit]
    return [{'passage_id':identifier,'lexical_similarity':round(float(value),6),
             'state':'candidate_to_review'} for identifier,value in ranked]


def evaluate_retrieval(cases: list[RetrievalCase],
                       corpus: list[tuple[str,str]], k_values: tuple[int,...]=(1,3,5)) -> dict:
    if not cases or not corpus or not k_values or any(k < 1 for k in k_values):
        raise ValueError('INVALID_EVALUATION_INPUT')
    ids={pid for pid,_ in corpus}
    if len(ids) != len(corpus):
        raise ValueError('DUPLICATE_PASSAGE')
    if len({c.query_id for c in cases}) != len(cases):
        raise ValueError('DUPLICATE_QUERY')
    per_language=defaultdict(list)
    for case in cases:
        if (case.language not in ('fr','en') or not case.relevant_passage_ids or
            not case.relevant_passage_ids <= ids):
            raise ValueError('INVALID_GROUND_TRUTH')
        rank=rank_passages(case.requirement,corpus,limit=len(corpus))
        items=[x['passage_id'] for x in rank]
        first=min((i+1 for i,pid in enumerate(items) if pid in case.relevant_passage_ids),default=None)
        single={'mrr':1/first if first else 0.0}
        for k in k_values:
            single[f'recall_at_{k}']=len(set(items[:k]) & case.relevant_passage_ids)/len(case.relevant_passage_ids)
        per_language[case.language].append(single)
    def aggregate(values):
        if not values:return None
        return {'queries':len(values),**{key:round(sum(v[key] for v in values)/len(values),4)
                for key in values[0]}}
    return {'baseline':'tfidf_char_3_5','all':aggregate([v for lang in per_language.values() for v in lang]),
            'by_language':{lang:aggregate(per_language[lang]) for lang in sorted(per_language)},
            'note':'Mesures sur passages annotés, pas sur l’embauche ou la valeur d’un candidat.'}


def propose_hard_negative_reviews(cases: list[RetrievalCase],
                                  corpus: list[tuple[str, str]],
                                  limit_per_query: int = 3) -> list[dict]:
    """Find lexically confusable passage candidates for EXPERT labeling.

    'negative' in the function name describes the intended annotation task, NOT
    an assigned label: unlabelled passages may still be relevant. Excludes known
    positives, but never automatically treats the remainder as nonrelevant.
    """
    if not 1 <= limit_per_query <= 20:
        raise ValueError('INVALID_LIMIT')
    proposals = []
    for case in cases:
        ranking = rank_passages(case.requirement, corpus, limit=len(corpus))
        for row in ranking:
            if row['passage_id'] in case.relevant_passage_ids:
                continue
            proposals.append({'query_id':case.query_id, 'passage_id':row['passage_id'],
                              'lexical_similarity':row['lexical_similarity'],
                              'state':'needs_expert_annotation',
                              'label':None})
            if sum(p['query_id']==case.query_id for p in proposals) >= limit_per_query:
                break
    return proposals
