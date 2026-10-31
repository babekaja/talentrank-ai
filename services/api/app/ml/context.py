"""Conservative context tagging of lexical skill mentions (fr/en, non-generative).

This is a triage heuristic, NOT an entailment model or a proficiency classifier.
Unknown, negative and hypothetical contexts are never automatically creditable.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

from app.ml.recognition import normalize

CONTEXT_VERSION = 'context-fr-en-2.0.0'

@dataclass(frozen=True)
class ContextDecision:
    status: str                 # mentioned | needs_review
    reason: str                 # deterministic, auditable reason code

# Intentionally conservative: queries, job requirements, learning goals and negations
# are not statements of acquired competence. Keep patterns small and testable.
_BEFORE = (
    ('negated', r'(?:sans|aucune?|pas|non|no|without|lack(?:ing)?|never|jamais|ni)\s+(?:(?:de|d|any|prior|previous|professional|pratique|real|actual|hands on)\s+){0,2}(?:experience|competences?|connaissances?|knowledge|maitrise|pratique|proficiency|skills?|training)(?:\s+(?:en|in|avec|with|de|of))?\s*$'),
    ('negated', r'(?:je\s+n\s+ai\s+jamais\s+(?:utilise|pratique|appris|maitrise)|i\s+have\s+never\s+(?:used|learned)|not\s+used|never\s+used|pas\s+utilise|ne\s+maitrise\s+pas|do\s+not\s+know)\s*$'),
    ('learning_only', r'(?:souhaite|veux|voudrais|aimerais|desire|want\s+to|plan\s+to|would\s+like\s+to|looking\s+to|en\s+train\s+d)\s+(?:(?:me|to)\s+)?(?:apprendre|learn|etudier|study|maitriser|master)\s*$'),
    ('learning_only', r'(?:en\s+cours\s+d\s+apprentissage|currently\s+learning|beginner\s+in|debutant\s+en|formation\s+en\s+cours\s+sur)\s*$'),
    ('requirement_only', r'(?:profil\s+recherche|competences\s+requises|poste\s+exige|recherche\s+un\s+profil|offre\s+d\s+emploi|candidate\s+must\s+know|required\s+skills?|looking\s+for|job\s+requirements|must\s+have)\s*$'),
    ('hypothetical', r'(?:si\s+j\s+apprenais|if\s+i\s+knew|would\s+like\s+experience\s+in|interesse\s+par|interested\s+in)\s*$'),
)
_AFTER = (
    ('negated', r'^\s*(?:(?:non|not)\s+(?:maitrise|mastered|used|acquis)|(?:aucune|no|sans|without)\s+experience|:?(?:\s*(?:debutant|beginner|novice))\b)'),
    ('learning_only', r'^\s*(?::|\-|\s)*(?:a\s+apprendre|to\s+learn|en\s+cours\s+d\s+apprentissage|currently\s+learning)\b'),
    ('hypothetical', r'^\s*(?:serait\s+un\s+plus|would\s+be\s+nice|a\s+etudier)\b'),
)


def classify_context(before: str, after: str, *, section: str = 'unknown') -> ContextDecision:
    """Classify mention using nearby SOURCE text (never generated paraphrases)."""
    if section in {'requirements', 'objectives'}:
        return ContextDecision('needs_review', 'section_' + section)
    preceding = normalize(before)[-180:]
    following = normalize(after)[:100]
    # Respect clause delimiters: a negation in the previous sentence must not carry over.
    # The caller clips to a sentence where possible; contrastive connectors further isolate it.
    preceding = re.split(r'\b(?:mais|but|however|toutefois|par\s+contre)\b', preceding)[-1]
    for code, pattern in _BEFORE:
        if re.search(pattern, preceding):
            return ContextDecision('needs_review', code)
    for code, pattern in _AFTER:
        if re.search(pattern, following):
            return ContextDecision('needs_review', code)
    return ContextDecision('mentioned', 'lexical_observation_only')
