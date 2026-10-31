"""Independent expert annotations for evidence/requirement matching.

Research-only, non-generative. Records are pseudonymised, documented excerpts;
no raw CVs or sensitive contact data are needed for training. Never interpret a
historical recruiting decision as a ground-truth skill label.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

LABELS = ('supports', 'related', 'insufficient')
SPLITS = ('train', 'calibration', 'test')


@dataclass(frozen=True)
class GoldPair:
    pair_id: str
    candidate_group: str
    document_group: str
    split: str
    language: str
    requirement: str
    evidence: str
    label: str
    source_hash: str
    evidence_sha256: str
    template_group: str
    page_number: int
    start_offset: int
    end_offset: int


def _check_record(row: dict) -> None:
    needed = {'pair_id', 'candidate_group', 'document_group', 'split', 'language',
              'requirement', 'evidence', 'source_hash', 'evidence_sha256',
              'template_group', 'page_number', 'start_offset', 'end_offset', 'reviews'}
    if not needed <= row.keys():
        raise ValueError('MISSING_ANNOTATION_FIELDS')
    if (not all(isinstance(row[k], str) and row[k].strip() for k in
               ('pair_id', 'candidate_group', 'document_group', 'requirement',
                'evidence', 'source_hash')) or
        row['split'] not in SPLITS or row['language'] not in ('fr', 'en') or
        not 2 <= len(row['requirement']) <= 500 or not 3 <= len(row['evidence']) <= 1000 or
        len(row['source_hash']) != 64 or
        any(c not in '0123456789abcdef' for c in row['source_hash'])):
        raise ValueError('INVALID_ANNOTATION_METADATA')
    if (not isinstance(row['evidence_sha256'], str) or
        row['evidence_sha256'] != sha256(row['evidence'].encode('utf-8')).hexdigest() or
        not isinstance(row['page_number'],int) or isinstance(row['page_number'],bool) or
        row['page_number'] < 1 or
        not isinstance(row['start_offset'],int) or isinstance(row['start_offset'],bool) or
        not isinstance(row['end_offset'],int) or isinstance(row['end_offset'],bool) or
        row['start_offset'] < 0 or row['end_offset'] - row['start_offset'] != len(row['evidence']) or
        not isinstance(row['template_group'],str) or not row['template_group'].strip()):
        raise ValueError('INVALID_SOURCE_PROVENANCE')
    reviews = row['reviews']
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise ValueError('TWO_INDEPENDENT_REVIEWS_REQUIRED')
    if (any(not isinstance(r, dict) or r.get('label') not in LABELS or
            not isinstance(r.get('reviewer'), str) or not r['reviewer'].strip()
            for r in reviews) or reviews[0]['reviewer'] == reviews[1]['reviewer']):
        raise ValueError('INVALID_INDEPENDENT_REVIEWS')
    if reviews[0]['label'] != reviews[1]['label']:
        adj = row.get('adjudication')
        if (not isinstance(adj, dict) or adj.get('label') not in LABELS or
            adj.get('reviewer') in (reviews[0]['reviewer'], reviews[1]['reviewer']) or
            not isinstance(adj.get('reviewer'), str) or not adj['reviewer'].strip()):
            raise ValueError('ADJUDICATION_REQUIRED')
    elif row.get('adjudication') is not None:
        raise ValueError('UNNECESSARY_ADJUDICATION')


def cohen_kappa(counts: list[tuple[str, str]]) -> float | None:
    """Unweighted κ for two annotators, not a model performance metric."""
    if not counts:
        return None
    observed = sum(a == b for a, b in counts) / len(counts)
    marg_a = Counter(a for a, _ in counts)
    marg_b = Counter(b for _, b in counts)
    expected = sum(marg_a[label] * marg_b[label] for label in LABELS) / len(counts) ** 2
    if expected == 1:
        return 1.0 if observed == 1 else None
    return round((observed - expected) / (1 - expected), 4)


def compile_gold(records: list[dict]) -> tuple[list[GoldPair], dict]:
    """Validate two-review annotation files, reject candidate/document/text leakage."""
    if not records:
        raise ValueError('EMPTY_ANNOTATIONS')
    seen_ids: set[str] = set()
    group_splits: dict[str, str] = {}
    document_splits: dict[str, str] = {}
    text_splits: dict[tuple[str, str], str] = {}
    template_splits: dict[str,str] = {}
    labels_by_split: dict[str, Counter] = {s: Counter() for s in SPLITS}
    comparisons: list[tuple[str, str]] = []
    output = []
    disagreements = 0
    for row in records:
        _check_record(row)
        pair_id = row['pair_id']
        if pair_id in seen_ids:
            raise ValueError('DUPLICATE_PAIR_ID')
        seen_ids.add(pair_id)
        split = row['split']
        for index, mapping in ((row['candidate_group'], group_splits),
                               (row['document_group'], document_splits)):
            if index in mapping and mapping[index] != split:
                raise ValueError('CANDIDATE_OR_DOCUMENT_LEAKAGE')
            mapping[index] = split
        family = row['template_group']
        if family in template_splits and template_splits[family] != split:
            raise ValueError('TEMPLATE_FAMILY_LEAKAGE')
        template_splits[family] = split
        # Also guard against verbatim pairs copied across candidate IDs.
        key = (' '.join(row['requirement'].casefold().split()),
               ' '.join(row['evidence'].casefold().split()))
        if key in text_splits and text_splits[key] != split:
            raise ValueError('DUPLICATED_TEXT_LEAKAGE')
        text_splits[key] = split
        a, b = (r['label'] for r in row['reviews'])
        comparisons.append((a, b))
        if a != b:
            disagreements += 1
        label = a if a == b else row['adjudication']['label']
        labels_by_split[split][label] += 1
        output.append(GoldPair(pair_id=pair_id,
              candidate_group=row['candidate_group'],
              document_group=row['document_group'],split=split,
              language=row['language'],requirement=row['requirement'],
              evidence=row['evidence'],label=label,source_hash=row['source_hash'],
              evidence_sha256=row['evidence_sha256'],template_group=family,
              page_number=row['page_number'],start_offset=row['start_offset'],
              end_offset=row['end_offset']))
    digest = sha256(json.dumps([
       [p.pair_id, p.candidate_group, p.document_group, p.split,
        p.language, p.requirement, p.evidence, p.label, p.source_hash, p.evidence_sha256,
        p.template_group, p.page_number, p.start_offset, p.end_offset]
       for p in sorted(output, key=lambda p:p.pair_id)],
       ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    report = {'dataset_sha256': digest, 'pairs': len(output),
              'disagreements': disagreements, 'raw_agreement': round(1 - disagreements/len(output), 4),
              'cohen_kappa': cohen_kappa(comparisons),
              'by_split': {k: dict(v) for k, v in labels_by_split.items()},
              'languages': dict(Counter(p.language for p in output)),
              'warning': 'Annotations de passages documentaires, jamais décisions RH.'}
    return output, report


def load_gold(path: Path) -> tuple[list[GoldPair], dict]:
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError('ANNOTATION_FILE_UNAVAILABLE_OR_TOO_LARGE')
    records = []
    with path.open('r', encoding='utf-8-sig') as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('INVALID_ANNOTATION_ROW')
                records.append(row)
    return compile_gold(records)


def verify_source_span(page_text: str, pair: GoldPair) -> bool:
    """Verify the exported passage still matches the ORIGINAL page text exactly.

    Does not authenticate the document itself: an authorized document fetch must
    separately compare the stored full-document SHA256 against the real bytes.
    """
    if not isinstance(page_text,str):
        raise TypeError('PAGE_TEXT_REQUIRED')
    a,b=pair.start_offset,pair.end_offset
    return (0<=a<b<=len(page_text)
            and page_text[a:b] == pair.evidence
            and sha256(page_text[a:b].encode('utf-8')).hexdigest()==pair.evidence_sha256)
