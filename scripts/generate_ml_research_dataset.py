"""Generate SYNTHETIC fake snippets, never real candidate details or invented metrics.

The synthetic labels are deterministic scaffolding for integration/regression tests,
NOT a valid dataset for measuring ML recruitment quality.
"""
from pathlib import Path
import hashlib,json

BASE=Path(__file__).resolve().parents[1]/'datasets'/'synthetic'
patterns={
'fr': {
'supports': [
  ('Développement Angular','J’ai créé des composants Angular et TypeScript pour une application de gestion.'),
  ('Développement API REST','J’ai développé des endpoints REST avec FastAPI pour un projet interne.'),
  ('Gestion des stocks','Gestion des stocks : inventaires, entrées et sorties enregistrés sur Excel.'),
  ('Administration MySQL','J’ai créé des index et optimisé des requêtes dans MySQL.'),
  ('Tests automatisés','Mise en place de tests automatisés avec pytest pour une API.'),
],
'related': [
  ('Développement Angular','J’ai programmé une interface web en HTML et JavaScript sans Angular.'),
  ('Développement API REST','J’ai utilisé une API REST existante, sans développer les endpoints.'),
  ('Gestion des stocks','J’ai coordonné des livraisons, sans réaliser la gestion des stocks.'),
  ('Administration MySQL','J’ai travaillé sur un tableau de bord connecté à PostgreSQL.'),
  ('Tests automatisés','J’ai assuré des vérifications manuelles des applications.'),
],
'insufficient': [
  ('Développement Angular','J’aimerais apprendre Angular dans les prochains mois.'),
  ('Développement API REST','Aucune expérience de conception d’API REST à ce jour.'),
  ('Gestion des stocks','Mon activité principale concernait la création de contenus pédagogiques.'),
  ('Administration MySQL','Je pratique la gestion d’événements associatifs.'),
  ('Tests automatisés','Je prévois une formation en tests logiciels.'),
]},
'en': {
'supports': [
  ('Angular development','Built reusable Angular components with TypeScript for a school application.'),
  ('REST API development','Designed and tested REST endpoints with Python FastAPI.'),
  ('Inventory management','Managed stock counts and reconciled warehouse inventory records.'),
  ('MySQL administration','Created MySQL indexes and repaired slow database queries.'),
  ('Automated testing','Wrote automated pytest tests for a backend service.'),
],
'related': [
  ('Angular development','Created a static webpage with JavaScript but not Angular.'),
  ('REST API development','Integrated a public REST service as a consumer only.'),
  ('Inventory management','Delivered supplies, but never maintained inventory records.'),
  ('MySQL administration','Built charts using data sourced from Microsoft Excel.'),
  ('Automated testing','Performed manual acceptance testing of user workflows.'),
],
'insufficient': [
  ('Angular development','I would like to learn Angular next semester.'),
  ('REST API development','No previous experience with building REST services.'),
  ('Inventory management','Helped organize conference registrations and badges.'),
  ('MySQL administration','I am interested in studying relational databases.'),
  ('Automated testing','Plans include studying software tests in the future.'),
]}}


def generate():
    # 72 pairs: 36 train, 18 calibration, 18 test. Independent, fictional groups.
    # Include near-miss cases; do not confuse absence of a skill with inability.
    rows=[]
    splits=(('train',36),('calibration',18),('test',18))
    n=0
    for split,count in splits:
        for i in range(count):
            n+=1
            label=('supports','related','insufficient')[i%3]
            language=('fr','en')[i%2]
            options=patterns[language][label]
            template_index = ((n // 6) % 3) if split == 'train' else (3 if split == 'calibration' else 4)
            req,passage=options[template_index]
            # Variation is synthetic background detail; keep meaning consistent.
            evidence=f'{passage} (Projet fictif n° {n}, exercice pédagogique.)'
            item={'pair_id':f'syn-pair-{n:03d}', 'candidate_group':f'synthetic-person-{n:03d}',
                  'document_group':f'synthetic-document-{n:03d}', 'split':split,
                  'language':language,'requirement':req,'evidence':evidence,
                  'source_hash':hashlib.sha256(evidence.encode()).hexdigest(),
                  'evidence_sha256':hashlib.sha256(evidence.encode()).hexdigest(),
                  'template_group':f'{language}-{label}-template-{template_index}',
                  'page_number':1,'start_offset':0,'end_offset':len(evidence),
                  'reviews':[{'reviewer':'annotator_A','label':label},
                             {'reviewer':'annotator_B','label':label}]}
            if n==13:
                item['reviews'][1]['label']='related'
                item['adjudication']={'reviewer':'expert_C','label':'supports'}
            rows.append(item)
    BASE.mkdir(parents=True,exist_ok=True)
    path=BASE/'evidence-triage-annotations.jsonl'
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    retrieval={'passages':[
      {'id':'p1','text':'Angular TypeScript components developed for school inventory system'},
      {'id':'p2','text':'Developed Python FastAPI REST endpoints and unit tests'},
      {'id':'p3','text':'I would like to learn Angular'},
      {'id':'p4','text':'Gestion des stocks de produits dans un entrepôt'},
      {'id':'p5','text':'Experience in event marketing and graphic design'},
      {'id':'p6','text':'MySQL indexing query optimization and migrations'}],
      'queries':[
      {'id':'q1','language':'en','requirement':'Angular development','relevant_passage_ids':['p1']},
      {'id':'q2','language':'en','requirement':'Python REST API backend','relevant_passage_ids':['p2']},
      {'id':'q3','language':'fr','requirement':'gestion des stocks','relevant_passage_ids':['p4']},
      {'id':'q4','language':'en','requirement':'MySQL administration','relevant_passage_ids':['p6']} ]}
    (BASE/'evidence-retrieval-benchmark.json').write_text(json.dumps(retrieval,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return path


if __name__=='__main__':
    print(generate())
