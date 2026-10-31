"""Traceable lexical/terminology skill recognition; similarity is never treated as proof.

spaCy segments the actual extracted text into contextual sentences. Character offsets refer
ALWAYS to the original, unmodified page text. Negated/aspirational references are flags.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

RULES_VERSION = 'lexical-spacy-2.0.0'


def normalize(value: str) -> str:
    text = unicodedata.normalize('NFKD', value.casefold())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = ''.join(c if c.isalnum() else ' ' for c in text)
    return ' '.join(text.split())


def normalized_with_positions(text: str) -> tuple[str, list[int], list[int]]:
    """Return normalized text and maps to ORIGINAL [start,end) char offsets."""
    output: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for i, char in enumerate(text):
        for transformed in unicodedata.normalize('NFKD', char.casefold()):
            if unicodedata.combining(transformed):
                continue
            if transformed.isalnum():
                output.append(transformed)
                starts.append(i)
                ends.append(i + 1)
            elif output and output[-1] != ' ':
                output.append(' ')
                starts.append(i)
                ends.append(i + 1)
    while output and output[-1] == ' ':
        output.pop(); starts.pop(); ends.pop()
    return ''.join(output), starts, ends


@lru_cache(maxsize=1)
def nlp_segmenter():
    import spacy
    nlp = spacy.blank('xx')  # tokenizer + deterministic sentence boundaries; no generative model
    nlp.add_pipe('sentencizer')
    nlp.max_length = 1_000_000
    return nlp


@dataclass(frozen=True)
class Detected:
    skill_id: str
    start: int
    end: int
    mention: str
    method: str
    status: str
    context_code: str = 'lexical_observation_only'


def check_context(context_before: str, context_after: str) -> str:
    """Backward-compatible two-state interface for older callers."""
    from app.ml.context import classify_context
    return classify_context(context_before, context_after).status


def extract_mentions(text: str, aliases: list[tuple[str, str, str]]) -> list[Detected]:
    """aliases are (skill-id, normalised alias, canonical normalised label)."""
    if not text.strip():
        return []
    normalized, starts, ends = normalized_with_positions(text)
    # One span may match multiple aliases; ambiguous collisions never become proof.
    patterns = sorted({a for _id, a, _canonical in aliases if a}, key=len, reverse=True)
    matches: list[tuple[int, int, str]] = []
    occupied: set[tuple[int, int]] = set()
    for alias in patterns:
        for found in re.finditer(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', normalized):
            if found.span() not in occupied:
                matches.append((found.start(), found.end(), alias)); occupied.add(found.span())
    # Avoid nested mentions of the same skill (e.g. "JavaScript" and "JS").
    matches.sort(key=lambda x: (x[0], -(x[1]-x[0])))
    sentence_spans = []
    if len(text) <= 250_000:
        try:
            sentence_spans = [(s.start_char, s.end_char) for s in nlp_segmenter()(text).sents]
        except ValueError:
            pass
    by_alias: dict[str, list[tuple[str, str]]] = {}
    for skill_id, alias, canonical in aliases:
        by_alias.setdefault(alias, []).append((skill_id, canonical))
    from app.ml.context import classify_context
    from app.ml.sections import section_at, section_lines
    lines = section_lines(text)
    detections: list[Detected] = []
    for a, b, alias in matches:
        start, end = starts[a], ends[b-1]
        preceding_start = max(0, start - 110)
        following_end = min(len(text), end + 50)
        for sent_start, sent_end in sentence_spans:
            if sent_start <= start < sent_end:
                preceding_start = max(preceding_start, sent_start)
                following_end = min(following_end, sent_end)
                break
        context = classify_context(text[preceding_start:start], text[end:following_end],
                                   section=section_at(start, lines))
        context_status = context.status
        context_code = context.reason
        # Ambiguous alias used for distinct concepts: never auto-credit either.
        if len({skill_id for skill_id, _ in by_alias[alias]}) > 1:
            context_status = 'needs_review'
            context_code = 'ambiguous_alias'
        for skill_id, canonical in by_alias[alias]:
            detections.append(Detected(skill_id, start, end, text[start:end],
                                       'canonical' if canonical == alias else 'verified_synonym',
                                       context_status, context_code))
    # If nested alias spans resolve to same skill, keep the longest mention.
    detections.sort(key=lambda d: (d.start, -(d.end-d.start)))
    filtered: list[Detected] = []
    for item in detections:
        if any(existing.skill_id == item.skill_id and existing.start <= item.start and existing.end >= item.end
               for existing in filtered):
            continue
        filtered.append(item)
    return filtered
