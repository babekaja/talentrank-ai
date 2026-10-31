"""Local embedding ranking of reference skill LABELS, for human review ONLY.

Similarities are raw cosines, never probabilities, equivalences, or hiring scores.
The caller provides reference IDs/labels, and must re-authorize them in SQL.
"""
from __future__ import annotations
import math
from typing import Protocol

class Embedder(Protocol):
    def encode(self, texts: list[str]): ...


def rank_labels(embedder: Embedder, query: str, labels: list[tuple[str, str]],
                *, limit: int = 8) -> list[dict]:
    if not 2 <= len(query.strip()) <= 250:
        raise ValueError('INVALID_QUERY')
    if not 1 <= len(labels) <= 120 or len({ref for ref, _ in labels}) != len(labels):
        raise ValueError('INVALID_CATALOGUE')
    if not 1 <= limit <= 20:
        raise ValueError('INVALID_LIMIT')
    vectors = embedder.encode([query.strip()] + [label for _, label in labels])
    if len(vectors) != len(labels) + 1:
        raise ValueError('VECTOR_COUNT_MISMATCH')
    ref = [float(x) for x in vectors[0]]
    size = len(ref)
    if not size or not all(math.isfinite(x) for x in ref):
        raise ValueError('INVALID_EMBEDDING')
    def cosine(vector):
        values = [float(x) for x in vector]
        if len(values) != size or not all(math.isfinite(x) for x in values):
            raise ValueError('INVALID_EMBEDDING')
        na = math.sqrt(sum(x*x for x in ref))
        nb = math.sqrt(sum(x*x for x in values))
        return sum(a*b for a,b in zip(ref, values)) / (na*nb) if na and nb else 0.0
    ranked = [{'skill_id':id_, 'similarity':round(cosine(vector), 6),
               'state':'candidate_to_review'} for (id_, _),vector in zip(labels, vectors[1:], strict=True)]
    return sorted(ranked, key=lambda r: (-r['similarity'], r['skill_id']))[:limit]
