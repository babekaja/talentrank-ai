"""Conservative quality flags based strictly on extracted source text.

No unverifiable inference, fraud labels, or inferred candidate attributes.
"""
from datetime import date
import re

# Only unambiguous day-first slash dates. Dates are not employment history extraction.
DATE_RE = re.compile(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)')


def inspect_pages(pages: list) -> list[dict]:
    findings=[]
    for p in pages:
        text=p.text or ''
        if not text.strip():
            findings.append({'page_number':p.page_number,'code':'NO_TEXT',
                             'severity':'review','message':'Aucun texte exploitable extrait de cette page.',
                             'source_excerpt':None})
            continue
        if len(text.strip())<25:
            findings.append({'page_number':p.page_number,'code':'SHORT_TEXT',
                             'severity':'review','message':'Texte très court : vérifier la lecture de cette page.',
                             'source_excerpt':text[:120]})
        for m in list(DATE_RE.finditer(text))[:30]:
            day,month,year=map(int,m.groups())
            try: date(year,month,day)
            except ValueError:
                findings.append({'page_number':p.page_number,'code':'INVALID_CALENDAR_DATE',
                    'severity':'review','message':'Date de calendrier invalide dans le texte extrait ; vérifier la source.',
                    'source_excerpt':text[max(0,m.start()-25):min(len(text),m.end()+25)]})
            if len(findings)>=100:
                return findings
    return findings
