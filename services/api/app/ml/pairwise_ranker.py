"""V11 CPU learning-to-rank research with *explicitly judged* pairs only.

Learns a preference between a labelled relevant passage and a labelled hard
negative for the SAME validated requirement. Neither unknown passages nor
unlabelled skills are training negatives. The result is a passage ranking
signal, NEVER proof of skills, proficiency, or suitability for employment.

The artifact is restricted, text-free JSON with finite, fixed-size parameters;
no pickle/joblib/untrusted deserialization is used.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import unicodedata

from app.ml.hybrid_retrieval import SourcePassage, _tokens
from app.ml.hybrid_evaluation import QueryLabel, validate_benchmark

VERSION = 'pairwise-linear-evidence-v11.0'
FEATURE_NAMES = (
    'query_token_recall', 'passage_token_precision', 'token_jaccard',
    'char_trigram_jaccard', 'char_fourgram_jaccard', 'query_bigram_recall',
    'documented_action_cue', 'negation_cue', 'learning_cue',
    'job_requirement_cue', 'conditional_cue',
)
# These are only source-language context cues, not comprehensive truth labels.
ACTION = re.compile(
    r'\b(?:developed|implemented|built|maintained|configured|deployed|designed|'
    r'oversaw|managed|administered|created|tested|wrote|developpe|concu|'
    r'realise|cree|configure|deploye|administre|gere|maintenance|effectue|'
    r'optimisation|gestion|utilise|implemented)\b', re.I)
NEGATED = re.compile(
    r'\b(?:sans experience|aucune experience|pas d experience|ne maitrise pas|'
    r'pas utilise|jamais utilise|never used|never worked|no experience|'
    r'without experience|do not know|does not know|lack experience|'
    r'have not used|no prior experience)\b', re.I)
LEARNING = re.compile(
    r'\b(?:souhaite apprendre|veux apprendre|en cours d apprentissage|'
    r'debute en|formation en cours|want to learn|would like to learn|'
    r'currently learning|plan to learn|interested in learning)\b', re.I)
REQUIREMENTS = re.compile(
    r'\b(?:job requirements?|required skills?|poste exige|competences requises|'
    r'candidate must|must have|profil recherche|recherche un candidat|'
    r'job advert(?:isement)?|offre d emploi)\b', re.I)
CONDITIONAL = re.compile(
    r'\b(?:if i knew|would be nice|si j apprenais|si je connaissais|'
    r'could learn|serait un plus)\b', re.I)


def _normalize(text: str) -> str:
    chars = unicodedata.normalize('NFKD', text.casefold())
    return re.sub(r'\s+', ' ', ''.join(c for c in chars if not unicodedata.combining(c)
                  and (c.isalnum() or c.isspace()))).strip()


def _ngrams(text: str, n: int) -> set[str]:
    normalized = _normalize(text)
    return {normalized[i:i+n] for i in range(max(0, len(normalized)-n+1))
            if normalized[i:i+n].strip()}


def _ratio_hit(a: set, b: set, mode: str) -> float:
    overlap = len(a & b)
    denom = len(a) if mode == 'recall' else len(b) if mode == 'precision' else len(a | b)
    return overlap / denom if denom else 0.0


def pair_features(requirement: str, passage: str) -> tuple[float, ...]:
    """Fixed vocabulary-free features, independent of any candidate attributes."""
    if (not isinstance(requirement, str) or not isinstance(passage, str) or
        not 2 <= len(requirement.strip()) <= 500 or
        not 2 <= len(passage.strip()) <= 5000):
        raise ValueError('INVALID_PAIR_TEXT')
    qt = _tokens(requirement)
    pt = _tokens(passage)
    qs, ps = set(qt), set(pt)
    q_bigrams = set(zip(qt, qt[1:]))
    p_bigrams = set(zip(pt, pt[1:]))
    normalized = _normalize(passage)
    features = (
        _ratio_hit(qs, ps, 'recall'),
        _ratio_hit(qs, ps, 'precision'),
        _ratio_hit(qs, ps, 'jaccard'),
        _ratio_hit(_ngrams(requirement, 3), _ngrams(passage, 3), 'jaccard'),
        _ratio_hit(_ngrams(requirement, 4), _ngrams(passage, 4), 'jaccard'),
        _ratio_hit(q_bigrams, p_bigrams, 'recall'),
        float(bool(ACTION.search(normalized))),
        float(bool(NEGATED.search(normalized))),
        float(bool(LEARNING.search(normalized))),
        float(bool(REQUIREMENTS.search(normalized))),
        float(bool(CONDITIONAL.search(normalized))),
    )
    if any(not math.isfinite(n) or not 0 <= n <= 1 for n in features):
        raise ValueError('INVALID_PAIR_FEATURE')
    return features


@dataclass(frozen=True)
class LinearPassageReranker:
    coefficients: tuple[float, ...]
    model_version: str = VERSION

    def __post_init__(self):
        if (self.model_version != VERSION or len(self.coefficients) != len(FEATURE_NAMES)
            or any(not math.isfinite(x) or abs(x) > 1e5 for x in self.coefficients)):
            raise ValueError('INVALID_RANKER_PARAMETERS')

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Ranks evidence snippets; the result is an uncalibrated utility, not a probability."""
        if len(pairs) > 1000:
            raise ValueError('RERANK_BATCH_TOO_LARGE')
        return [sum(w*x for w, x in zip(self.coefficients, pair_features(q, p)))
                for q, p in pairs]


def train_pairwise(passages: list[SourcePassage], queries: list[QueryLabel], *,
                   regularization: float = 1.0) -> tuple[LinearPassageReranker, dict]:
    """Train on **only** positively and explicitly hard-negative judged pairs."""
    from sklearn.linear_model import LogisticRegression
    validate_benchmark(passages, queries)
    if not 0.01 <= regularization <= 100 or not math.isfinite(regularization):
        raise ValueError('INVALID_REGULARIZATION')
    indexed = {p.passage_id: p for p in passages}
    vectors, labels, n_pairs = [], [], 0
    for q in sorted(queries, key=lambda x: x.query_id):
        positives = [pair_features(q.requirement, indexed[pid].text)
                     for pid in sorted(q.relevant_passage_ids)]
        negatives = [pair_features(q.requirement, indexed[pid].text)
                     for pid in sorted(q.hard_negative_passage_ids)]
        for positive in positives:
            for negative in negatives:
                difference = [a-b for a, b in zip(positive, negative)]
                vectors.extend((difference, [-value for value in difference]))
                labels.extend((1, 0))
                n_pairs += 1
    if n_pairs < 6:
        raise ValueError('INSUFFICIENT_JUDGED_PAIRS')
    model = LogisticRegression(C=regularization, fit_intercept=False,
                               solver='liblinear', max_iter=2000, random_state=11)
    model.fit(vectors, labels)
    weights = tuple(float(w) for w in model.coef_[0])
    return LinearPassageReranker(weights), {'judged_preference_pairs': n_pairs,
        'training_queries': len(queries), 'regularization_c': regularization,
        'unjudged_passages_as_negatives': False, 'training_method': 'pairwise_logistic_l2',
        'calibrated_probability': False, 'feature_names': list(FEATURE_NAMES)}


def save_ranker(path: Path, model: LinearPassageReranker, *,
                training_sha256: str, split_sha256: str, training_info: dict) -> None:
    """Text-free artifact; digest detects accidental corruption, not authenticity."""
    if not re.fullmatch(r'[a-f0-9]{64}', training_sha256) or not re.fullmatch(r'[a-f0-9]{64}', split_sha256):
        raise ValueError('INVALID_TRAINING_DIGEST')
    payload = {'version': VERSION, 'features': list(FEATURE_NAMES),
               'coefficients': list(model.coefficients),
               'training_dataset_sha256': training_sha256,
               'group_manifest_sha256': split_sha256,
               'training_info': training_info,
               'usage': 'offline_passage_ordering_research_only'}
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    envelope = {'payload': payload, 'integrity_sha256': sha256(body.encode('utf-8')).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_ranker(path: Path) -> LinearPassageReranker:
    """No arbitrary code execution: strict bounded JSON, coefficients only."""
    if not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError('INVALID_RANKER_FILE')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or set(obj) != {'payload', 'integrity_sha256'}:
        raise ValueError('INVALID_RANKER_FORMAT')
    data = obj['payload']
    if not isinstance(data, dict) or set(data) != {'version', 'features', 'coefficients',
       'training_dataset_sha256', 'group_manifest_sha256', 'training_info', 'usage'}:
        raise ValueError('INVALID_RANKER_FORMAT')
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    if not isinstance(obj['integrity_sha256'], str) or sha256(canonical.encode('utf-8')).hexdigest() != obj['integrity_sha256']:
        raise ValueError('RANKER_INTEGRITY_MISMATCH')
    if (data['version'] != VERSION or data['features'] != list(FEATURE_NAMES) or
        data['usage'] != 'offline_passage_ordering_research_only'):
        raise ValueError('INCOMPATIBLE_RANKER')
    if not isinstance(data['coefficients'], list) or any(type(x) not in (float, int) for x in data['coefficients']):
        raise ValueError('INVALID_RANKER_PARAMETERS')
    return LinearPassageReranker(tuple(data['coefficients']), data['version'])
