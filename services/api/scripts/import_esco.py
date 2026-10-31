"""Offline ESCO CSV import (from an independently downloaded official ESCO package).

No automated acceptance of 'altLabels' or qualification equivalence. Imported concepts
start inactive until checked; the official URI and declared release are preserved.
"""
import argparse
import csv
from pathlib import Path
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Skill


def import_esco(path: Path, version: str, language: str, db) -> tuple[int,int]:
    if language not in ('en','fr'):
        raise ValueError('Only en/fr ESCO columns are supported in this importer')
    created,seen=0,0
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        # Common ESCO distributed CSV layout; explicit aliases for backwards compatibility.
        if not {'conceptUri','preferredLabel'}.issubset(reader.fieldnames or []):
            raise ValueError('ESCO CSV must have conceptUri and preferredLabel columns')
        for row in reader:
            uri=(row.get('conceptUri') or '').strip()
            label=(row.get('preferredLabel') or '').strip()
            kind=(row.get('conceptType') or '').strip().lower()
            if kind and kind not in ('skill','knowledge','competence','sk'):
                continue  # groups and occupations must not be mistaken for skills
            if not uri.startswith('http://data.europa.eu/esco/skill/') or not label or len(label)>180:
                continue
            seen+=1
            skill=db.scalar(select(Skill).where(Skill.external_uri==uri))
            if skill is None:
                skill=Skill(code='esco-'+uri.rsplit('/',1)[-1],label_fr=label if language=='fr' else 'Non traduit',
                            label_en=label if language=='en' else 'Not translated',
                            taxonomy='esco',external_uri=uri,version=version,active=False)
                db.add(skill)
                created+=1
            else:
                if language=='fr':skill.label_fr=label
                else:skill.label_en=label
        db.commit()
    return created,seen

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('csv_path',type=Path)
    parser.add_argument('--version',required=True)
    parser.add_argument('--language',choices=['fr','en'],required=True)
    args=parser.parse_args()
    with SessionLocal() as db:
        count,total=import_esco(args.csv_path,args.version,args.language,db)
        print(f'{total} concepts ESCO traités; {count} nouveaux, inactifs avant validation humaine.')
