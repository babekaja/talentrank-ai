"""Controlled fairness smoke checks: professional signal must not depend on identity metadata."""
from dataclasses import dataclass
from app.ml.recognition import extract_mentions, normalize

@dataclass(frozen=True)
class Profile:
    identity_label:str
    professional_text:str

def identity_invariance(professional_text:str, identity_labels:list[str], aliases:list[tuple[str,str,str]])->dict:
    if not 5<=len(professional_text)<=4000 or not 2<=len(identity_labels)<=8 or any(not 1<=len(x)<=100 for x in identity_labels):
        raise ValueError('Entrées du test inadéquates')
    # Test the REAL lexical extractor on synthetic document variants. Never store labels.
    # This may reveal name-induced false positives or context spillover.
    baseline=sorted((x.skill_id,x.status,x.context_code) for x in extract_mentions(professional_text,aliases))
    signatures=[]
    for label in identity_labels:
        variant=f'Nom du profil fictif : {label}\n\n{professional_text}'
        detected=sorted((x.skill_id,x.status,x.context_code) for x in extract_mentions(variant,aliases))
        signatures.append(detected)
    return {'invariant':all(v==baseline for v in signatures),'variant_count':len(identity_labels),
            'observed_skill_mentions':len(baseline),
            'status':'synthetic_counterfactual_sanity_check_only',
            'limitations':['Les variantes du nom synthétique sont réellement transmises à l’extracteur lexical; ce test peut détecter des faux positifs liés à l’en-tête.',
                           'Ce test ne mesure pas les biais indirects, de groupe ni la qualité d’extraction.',
                           'Aucune caractéristique protégée ni identité transmise n’est conservée.']}
