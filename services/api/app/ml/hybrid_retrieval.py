"""Phase 10: offline evidence-PASSAGE retrieval, never candidate scoring.

Two independent lexical retrievers (BM25 and character TF-IDF), optional local
sentence embeddings, reciprocal-rank fusion, optional local CrossEncoder rerank.
All returned records are *unverified review candidates* with source pointers.
Tenant/document filtering happens BEFORE any model sees the text.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import math
import re
import unicodedata
from typing import Protocol, Sequence

RETRIEVAL_VERSION = 'passage-hybrid-rrf-v10.0'


@dataclass(frozen=True)
class SourcePassage:
    passage_id: str
    organization_id: str
    document_id: str
    page_number: int
    start_offset: int
    text: str

    @property
    def end_offset(self) -> int:
        return self.start_offset + len(self.text)

    @property
    def text_sha256(self) -> str:
        return sha256(self.text.encode('utf-8')).hexdigest()


class Embedder(Protocol):
    def encode(self, texts: list[str]): ...


class Reranker(Protocol):
    def predict(self, pairs: list[tuple[str, str]]): ...


def check_source(page_text: str, p: SourcePassage) -> bool:
    """Check the EXTRACTED page span; document-byte hash must be verified separately."""
    return (isinstance(page_text, str) and 0 <= p.start_offset < p.end_offset <= len(page_text)
            and page_text[p.start_offset:p.end_offset] == p.text)


def _tokens(text: str) -> list[str]:
    decomposed = unicodedata.normalize('NFKD', text.casefold())
    plain = ''.join(x for x in decomposed if not unicodedata.combining(x))
    return re.findall(r'[a-z0-9]+(?:[+#][a-z0-9]*)?', plain)


def bm25_scores(query: str, texts: Sequence[str], *, k1: float = 1.2,
                b: float = 0.75) -> list[float]:
    """Simple Okapi BM25, IDF with +1 smoothing; deterministic CPU implementation."""
    if not texts or not 0 < k1 <= 3 or not 0 <= b <= 1:
        raise ValueError('INVALID_BM25_INPUT')
    terms = set(_tokens(query))
    docs = [Counter(_tokens(t)) for t in texts]
    mean_length = sum(sum(c.values()) for c in docs) / len(docs)
    df = Counter(term for d in docs for term in d)
    output = []
    for counts in docs:
        dl = sum(counts.values())
        norm = k1 * (1 - b + b * dl / max(1e-12, mean_length))
        score = 0.0
        for term in terms & counts.keys():
            freq = counts[term]
            idf = math.log1p((len(docs) - df[term] + .5) / (df[term] + .5))
            score += idf * freq * (k1 + 1) / (freq + norm)
        output.append(score)
    return output


def _tfidf_scores(query: str, texts: Sequence[str]) -> list[float]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                          strip_accents='unicode', sublinear_tf=True)
    try:
        matrix = vec.fit_transform([query, *texts])
    except ValueError as exc:
        if 'empty vocabulary' in str(exc).lower():
            return [0.0] * len(texts)
        raise
    return [float(v) for v in cosine_similarity(matrix[0], matrix[1:]).ravel()]


def _dense_scores(query: str, texts: Sequence[str], embedder: Embedder) -> list[float]:
    vectors = embedder.encode([query, *texts])
    if len(vectors) != len(texts) + 1:
        raise ValueError('INVALID_EMBEDDING_COUNT')
    ref = [float(x) for x in vectors[0]]
    if not ref or any(not math.isfinite(x) for x in ref):
        raise ValueError('INVALID_EMBEDDING_VALUES')
    norm_ref = math.sqrt(sum(x*x for x in ref))
    scores = []
    for vector in vectors[1:]:
        candidate = [float(x) for x in vector]
        if len(candidate) != len(ref) or any(not math.isfinite(x) for x in candidate):
            raise ValueError('INVALID_EMBEDDING_VALUES')
        norm = math.sqrt(sum(x*x for x in candidate))
        scores.append(sum(a*b for a,b in zip(ref,candidate)) / (norm_ref*norm)
                      if norm_ref and norm else 0.0)
    return scores


def _ordered(scores: Sequence[float], passages: Sequence[SourcePassage]) -> list[str]:
    if len(scores) != len(passages) or any(not math.isfinite(float(s)) for s in scores):
        raise ValueError('INVALID_RETRIEVAL_SCORE')
    return [p.passage_id for _,p in sorted(zip(scores,passages),
               key=lambda pair: (-float(pair[0]), pair[1].passage_id))]


def fuse_rrf(rankings: dict[str, list[str]], *, constant: int = 60) -> list[tuple[str, float]]:
    """RRF uses RANKS, not incomparable BM25, cosine or CrossEncoder scales."""
    if not rankings or not 1 <= constant <= 1000:
        raise ValueError('INVALID_RRF_INPUT')
    scores: dict[str, float] = {}
    for ranking in rankings.values():
        if len(set(ranking)) != len(ranking):
            raise ValueError('DUPLICATED_RANKING_ITEM')
        for position, identifier in enumerate(ranking, 1):
            if not identifier:
                raise ValueError('EMPTY_RANKING_ID')
            scores[identifier] = scores.get(identifier, 0.0) + 1.0/(constant+position)
    return sorted(scores.items(), key=lambda row:(-row[1],row[0]))


def retrieve_passages(query: str, passages: Sequence[SourcePassage], *,
                      organization_id: str, authorized_documents: frozenset[str],
                      embedder: Embedder | None = None,
                      reranker: Reranker | None = None,
                      top_k: int = 10, rerank_top_n: int = 20) -> dict:
    """Offline search. Permissions MUST be resolved by the caller against SQL.

    The only purpose of this API is to suggest passages to inspect; every hit
    remains unconfirmed regardless of score. Never call it on a whole CV list
    to silently rank people or evaluate employability.
    """
    if not isinstance(query,str) or not 2 <= len(query.strip()) <= 500:
        raise ValueError('INVALID_QUERY')
    if (not organization_id or not authorized_documents or
        not 1 <= top_k <= 100 or not 1 <= rerank_top_n <= 100 or
        (reranker is not None and rerank_top_n < top_k)):
        raise ValueError('INVALID_RETRIEVAL_SCOPE')
    seen = set()
    for p in passages:
        if (not isinstance(p,SourcePassage) or not p.passage_id or p.passage_id in seen or
            not p.organization_id or not p.document_id or
            p.page_number < 1 or p.start_offset < 0 or not p.text.strip() or
            len(p.text) > 5000):
            raise ValueError('INVALID_PASSAGE')
        seen.add(p.passage_id)
    # Critical: do not send unauthorized text to embeddings or reranker.
    permitted = [p for p in passages if p.organization_id == organization_id
                 and p.document_id in authorized_documents]
    if not permitted:
        return {'pipeline':RETRIEVAL_VERSION, 'methods': [], 'items': [],
                'candidate_count':0, 'disclaimer':'Aucune preuve confirmée.'}
    texts = [p.text for p in permitted]
    rankings = {'bm25': _ordered(bm25_scores(query,texts),permitted),
                'tfidf_char': _ordered(_tfidf_scores(query,texts),permitted)}
    if embedder is not None:
        rankings['dense'] = _ordered(_dense_scores(query,texts,embedder),permitted)
    fused = fuse_rrf(rankings)
    ids = {p.passage_id:p for p in permitted}
    selected = fused[:max(top_k,rerank_top_n) if reranker else top_k]
    rerank_values = {}
    if reranker is not None:
        pairs = [(query, ids[pid].text) for pid,_ in selected[:rerank_top_n]]
        raw = reranker.predict(pairs)
        if len(raw) != len(pairs):
            raise ValueError('INVALID_RERANK_COUNT')
        for (pid,_), score in zip(selected[:rerank_top_n],raw):
            value=float(score)
            if not math.isfinite(value):
                raise ValueError('INVALID_RERANK_SCORE')
            rerank_values[pid] = value
        # Rerank only the inspected head, preserve original order as a tie-breaker.
        head = selected[:rerank_top_n]
        head = sorted(enumerate(head), key=lambda x:(-rerank_values[x[1][0]],x[0]))
        selected = [row for _,row in head] + selected[rerank_top_n:]
    items = []
    for pid, fused_score in selected[:top_k]:
        p = ids[pid]
        item = {'passage_id':pid, 'document_id':p.document_id,
                'page_number':p.page_number, 'start_offset':p.start_offset,
                'end_offset':p.end_offset,'text_sha256':p.text_sha256,
                'rrf_score':round(fused_score,8),
                'status':'unverified_passage_for_human_review',
                'supports_requirement':None}
        if pid in rerank_values:
            item['reranker_raw_score'] = round(rerank_values[pid],6)
        items.append(item)
    return {'pipeline':RETRIEVAL_VERSION, 'methods':list(rankings) +
            (['cross_encoder'] if reranker is not None else []),
            'candidate_count':len(permitted),'items':items,
            'disclaimer':'Scores de recherche et de tri de passages; aucune compétence, équivalence ou décision RH confirmée.'}
