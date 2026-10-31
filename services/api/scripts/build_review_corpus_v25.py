"""Generate consent-free, ENTIRELY SYNTHETIC FR/EN CVs and blank double-review sheets.

Engineering-only expected labels are held separately and MUST NOT be supplied to
reviewers. All names, organizations, contact details and achievements are invented.
The output is NOT an independently human-annotated or scientifically valid corpus.
"""
from __future__ import annotations
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import random
import zipfile
from docx import Document

CONCEPTS = [
    ('Angular', 'Angular', 'J’ai développé un portail Angular et TypeScript.', 'I built an Angular and TypeScript portal.',
     'Je souhaite apprendre Angular cette année.', 'I plan to learn Angular this year.'),
    ('Python', 'Python', 'J’ai automatisé des rapports avec Python.', 'I automated reporting with Python.',
     'Je commence à découvrir Python.', 'I am starting to learn Python.'),
    ('SQL', 'SQL', 'J’ai conçu des requêtes SQL pour une base relationnelle.', 'I wrote SQL queries for a relational database.',
     'Aucune pratique des requêtes SQL.', 'No hands-on SQL query experience.'),
    ('Git', 'Git', 'J’ai utilisé Git pour gérer des contributions à un projet.', 'I used Git to manage project contributions.',
     'Git est requis pour le poste souhaité.', 'Git is required for the desired role.'),
    ('Docker', 'Docker', 'J’ai construit et exécuté des conteneurs Docker.', 'I built and ran Docker containers.',
     'Docker figure parmi les compétences à acquérir.', 'Docker is among the skills I want to learn.'),
    ('FastAPI', 'FastAPI', 'J’ai développé une API REST avec FastAPI.', 'I developed a REST API using FastAPI.',
     'Je n’ai jamais utilisé FastAPI.', 'I have never used FastAPI.'),
    ('Supply Chain', 'Supply Chain', 'J’ai organisé des livraisons et suivi les stocks.', 'I organized deliveries and tracked inventory.',
     'Je souhaite suivre une formation en logistique.', 'I want to take a course in logistics.'),
    ('Excel', 'Excel', 'J’ai construit des tableaux de suivi avec Excel.', 'I built tracking spreadsheets with Excel.',
     'Excel figure dans une liste de logiciels à apprendre.', 'Excel appears in a list of tools to learn.'),
    ('Tests logiciels', 'Software Testing', 'J’ai écrit des tests unitaires pour un logiciel.', 'I wrote unit tests for software.',
     'Je dois encore apprendre les tests automatisés.', 'I still need to learn automated tests.'),
    ('Gestion de projet', 'Project Management', 'J’ai coordonné les tâches d’une équipe projet.', 'I coordinated a project team’s tasks.',
     'Je cherche un poste de gestionnaire de projet.', 'I am looking for a project manager role.'),
    ('React', 'React', 'J’ai créé une interface React pour un portail.', 'I developed a React interface for a portal.',
     'Je n’ai aucune expérience en React.', 'I have no experience with React.'),
    ('Administration Linux', 'Linux Administration', 'J’ai administré un serveur Linux de laboratoire.', 'I administered a lab Linux server.',
     'Linux est prévu dans mon plan de formation.', 'Linux is on my training roadmap.'),
    ('MySQL', 'MySQL', 'J’ai conçu des tables et index sous MySQL.', 'I designed tables and indexes in MySQL.',
     'J’ai seulement entendu parler de MySQL.', 'I have only heard of MySQL.'),
    ('Analyse de données', 'Data Analysis', 'J’ai nettoyé et analysé des données avec pandas.', 'I cleaned and analyzed data using pandas.',
     'Je souhaiterais apprendre l’analyse de données.', 'I would like to learn data analysis.'),
    ('Support client', 'Customer Support', 'J’ai assuré le suivi des demandes de clients.', 'I handled customer support requests.',
     'Le support client m’intéresse sans expérience pratique.', 'Customer support interests me but I have no practical experience.'),
    ('Design UI', 'UI Design', 'J’ai conçu des maquettes accessibles pour une application.', 'I designed accessible mockups for an application.',
     'Je recherche une formation en conception d’interfaces.', 'I am looking for interface design training.'),
    ('Power BI', 'Power BI', 'J’ai construit des tableaux de bord avec Power BI.', 'I built dashboards with Power BI.',
     'Power BI est un outil que je veux essayer.', 'Power BI is a tool I would like to try.'),
    ('Réseaux', 'Computer Networking', 'J’ai configuré des équipements de réseau local.', 'I configured local network equipment.',
     'Je n’ai pas encore de pratique des réseaux.', 'I have no hands-on network experience yet.'),
    ('Statistiques', 'Statistics', 'J’ai appliqué des statistiques descriptives à une enquête.', 'I performed descriptive statistical analysis on a survey.',
     'J’aimerais approfondir mes connaissances en statistiques.', 'I would like to study statistics further.'),
    ('Cyber sécurité', 'Cybersecurity', 'J’ai effectué une revue des permissions d’une application.', 'I reviewed an application’s access controls.',
     'Je souhaite travailler un jour en cybersécurité.', 'I hope to work in cybersecurity someday.'),
]
FIELDS = ('task_id','doc_id','split','language','criterion','passage','reviewer_label','confidence','comment')


def build(output: Path, count: int=400, seed: int=20261011) -> dict:
    if count < 20 or count > 3000:
        raise ValueError('Count must be between 20 and 3000')
    output.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed)
    tasks=[]; engineering=[]; hashes={}
    zip_path=output/'SYNTHETIC-CVs.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for i in range(count):
            concept=CONCEPTS[i%len(CONCEPTS)]
            lang='fr' if (i//len(CONCEPTS))%2==0 else 'en'
            path_type=('university','alternative','informal','project')[i%4]
            suffix=f'Référence strictement fictive {i:04d}-{rng.randrange(1_000_000):06d}'
            direct=(concept[2] if lang=='fr' else concept[3])+' '+suffix
            warning=(concept[4] if lang=='fr' else concept[5])+' '+suffix
            doc=Document()
            doc.add_heading(('CV FICTIF' if lang=='fr' else 'FICTIONAL RESUME')+f' — {i:04d}',0)
            doc.add_paragraph('DOCUMENT SYNTHÉTIQUE — PERSONNE INEXISTANTE — INTERDIT COMME CV RÉEL')
            doc.add_heading('Projets' if path_type in ('project','informal') else ('Experience' if lang=='en' else 'Expérience'),level=1)
            doc.add_paragraph(direct)
            doc.add_heading('Objectives' if lang=='en' else 'Objectifs',level=1)
            doc.add_paragraph(warning)
            doc.add_paragraph(f'Parcours fictif / Fictional route: {path_type}. Aucune identité personnelle.')
            stream=io.BytesIO();doc.save(stream)
            raw=stream.getvalue()
            filename=f'SYNTH-CV-{i:04d}.docx'
            archive.writestr(filename,raw)
            hashes[filename]=sha256(raw).hexdigest()
            for label,passage in [('supports',direct),('insufficient',warning)]:
                task_id=f'task-{i:04d}-{label}'
                tasks.append({'task_id':task_id,'doc_id':f'doc-{i:04d}',
                    'split':('train' if i%20<12 else 'validation' if i%20<16 else 'test'),
                    'language':lang,'criterion':concept[0] if lang=='fr' else concept[1],
                    'passage':passage,'reviewer_label':'','confidence':'','comment':''})
                engineering.append({'task_id':task_id,'generator_expected_label':label,
                                    'origin':'synthetic_generator_not_human_annotation'})
    # Two different, independently fillable empty forms. DO NOT claim two annotations were performed.
    for person in ('A','B'):
        rows=tasks.copy();random.Random(seed+ord(person)).shuffle(rows)
        with (output/f'annotation-reviewer-{person}-BLANK.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    (output/'engineering-expected-labels-NOT-HUMAN.json').write_text(json.dumps(engineering,ensure_ascii=False,indent=2),encoding='utf-8')
    info={'kind':'synthetic_engineering_corpus','cv_count':count,'task_count':len(tasks),
          'annotations_completed':0,'independent_human_reviewers':0,
          'license':'Generated specifically for project tests; no real person or third-party data',
          'generator':'build_review_corpus_v25.py','seed':seed,
          'cv_sha256':hashes,'claim':'Never use this corpus as human-labeled evidence of accuracy'}
    (output/'MANIFEST-SYNTHETIC.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    return {'cv_count':count,'tasks':len(tasks),'archive_bytes':zip_path.stat().st_size,'manifest':str(output/'MANIFEST-SYNTHETIC.json')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=400)
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.count),ensure_ascii=False))

if __name__=='__main__':main()
