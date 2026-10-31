"""Source-grounded, deterministic French/English CV section extraction.

Extract only literal lines inside explicitly headed sections. Do not infer dates,
professional seniority, degrees, organizations, competence or diploma equivalence.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from app.ml.recognition import normalize

SECTIONS_VERSION = 'sections-fr-en-1.0.0'
HEADINGS = {
    'experience': {'experience', 'experiences', 'experience professionnelle', 'experiences professionnelles',
                   'parcours professionnel', 'professional experience', 'work experience', 'employment history',
                   'work history', 'emplois', 'stages', 'internships'},
    'education': {'formation', 'formations', 'formation academique', 'parcours academique',
                  'education', 'academic background', 'education and training', 'etudes', 'diplomes'},
    'projects': {'projets', 'projets personnels', 'projets realises', 'realisations',
                 'projects', 'personal projects', 'portfolio', 'selected projects'},
    'skills': {'competences', 'competences techniques', 'skills', 'technical skills',
               'technologies', 'outils et technologies'},
    'objectives': {'objectif', 'objectifs', 'profil recherche', 'objective', 'career objective',
                   'professional objective', 'objectif professionnel'},
    'requirements': {'competences requises', 'exigences du poste', 'job requirements',
                     'required skills', 'profil du poste', 'offre d emploi'},
    'other': {'contact', 'coordonnees', 'langues', 'languages', 'references', 'references professionnelles',
              'interets', 'interests', 'summary', 'profil', 'profile', 'a propos', 'about me'},
}
HEADING_LOOKUP = {normalize(v): key for key, values in HEADINGS.items() for v in values}
DATE_MARKER = re.compile(r'\b(?:19|20)\d{2}\b|\b(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:19|20)\d{2}\b', re.I)

@dataclass(frozen=True)
class SectionLine:
    section: str
    start: int
    end: int
    text: str


def section_lines(page_text: str, initial_section: str = 'unknown') -> list[SectionLine]:
    """Return exact original-text offsets of each data line with its most recent heading."""
    section = initial_section
    results = []
    for line in re.finditer(r'[^\r\n]*(?:\r?\n|$)', page_text):
        source = line.group(0).rstrip('\r\n')
        if not source.strip():
            continue
        candidate = normalize(source.strip().strip(':').strip('–—- '))
        if len(source.strip()) <= 75 and candidate in HEADING_LOOKUP:
            section = HEADING_LOOKUP[candidate]
            continue
        if len(source.strip()) <= 80 and candidate.endswith(' :') and candidate[:-2] in HEADING_LOOKUP:
            section = HEADING_LOOKUP[candidate[:-2]]
            continue
        start = line.start() + len(source) - len(source.lstrip())
        end = line.start() + len(source.rstrip())
        if end > start:
            results.append(SectionLine(section, start, end, page_text[start:end]))
    return results


def section_at(offset: int, lines: list[SectionLine]) -> str:
    for item in lines:
        if item.start <= offset < item.end:
            return item.section
    return 'unknown'


def extract_source_facts(page_text: str) -> list[SectionLine]:
    """Literal spans, not structured claims. Designed as reviewable candidate facts."""
    facts=[]
    for line in section_lines(page_text):
        if line.section not in {'experience','education','projects'}:
            continue
        cleaned = line.text.strip().lstrip('•-*– ').strip()
        if not (3 <= len(cleaned) <= 350) or not re.search(r'[\w\u00c0-\u017f]', cleaned):
            continue
        # Preserve the entire literal line, including any dates, without deriving a duration.
        facts.append(line)
    return facts
