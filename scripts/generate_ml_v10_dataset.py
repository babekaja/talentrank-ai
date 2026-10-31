"""Reproducible entirely FICTIONAL retrieval cases. No private candidate data."""
import json
from pathlib import Path

PASSAGES = [
 ('p01','J’ai développé une application de gestion avec Angular et TypeScript.'),
 ('p02','Je souhaite apprendre Angular dans les prochaines semaines.'),
 ('p03','Built Angular components with TypeScript for a school management application.'),
 ('p04','I have no professional experience using Angular.'),
 ('p05','Conception et maintenance de services API REST avec FastAPI et Python.'),
 ('p06','Implemented Python FastAPI REST endpoints with validation and tests.'),
 ('p07','Job requirements: Python REST API and FastAPI are essential.'),
 ('p08','Gestion des stocks, inventaires mensuels et suivi des approvisionnements.'),
 ('p09','Oversaw inventory management and warehouse stock counts for a small retailer.'),
 ('p10','Interested in an inventory management position but no experience yet.'),
 ('p11','Administration de PostgreSQL avec sauvegardes et optimisation SQL.'),
 ('p12','Optimisation de requêtes MySQL, index et migrations de schéma.'),
 ('p13','Worked with Microsoft SQL Server database administration.'),
 ('p14','J’aimerais apprendre le langage Python à l’avenir.'),
 ('p15','Développement d’un script Python pour analyser des fichiers CSV.'),
 ('p16','Used Git branches and pull requests to coordinate code reviews.'),
 ('p17','Created Docker images and Compose stacks for deploying an internal service.'),
 ('p18','Maintained Kubernetes workloads and configured deployment manifests.'),
 ('p19','Je commence seulement à apprendre Docker, sans pratique.'),
 ('p20','Wrote automated pytest unit tests and integration tests for API services.'),
 ('p21','I have never written automated tests using pytest.'),
 ('p22','Stage de développement web : interfaces React et tests de composants.'),
 ('p23','Built React hooks and interactive UI forms.'),
 ('p24','Used spreadsheet and word processing software in an office.'),
 ('p25','Competences requises : Docker, Angular, Python et Git.'),
 ('p26','Automated database backups and schema migrations in MySQL.'),
 ('p27','Piloted stock reconciliation and warehouse inventory controls.'),
 ('p28','Mise en production de conteneurs Docker pour un projet associatif.'),
 ('p29','Développement de tests automatisés avec pytest pour un service web.'),
 ('p30','Je sais seulement ouvrir une application sur un navigateur.'),
]
CASES = [
 ('q01','fr','développement Angular','p01',['p02','p04','p25']),
 ('q02','en','Angular front-end development','p03',['p02','p04','p25']),
 ('q03','fr','création API REST Python FastAPI','p05',['p07','p14']),
 ('q04','en','Python backend REST endpoints','p06',['p07','p14']),
 ('q05','fr','gestion de stock et inventaire','p08',['p10']),
 ('q06','en','warehouse inventory management','p09',['p10']),
 ('q07','fr','administration MySQL','p12',['p24']),
 ('q08','en','MySQL database backups','p26',['p24']),
 ('q09','fr','gestion de conteneurs Docker','p28',['p19','p25']),
 ('q10','en','build Docker images','p17',['p19','p25']),
 ('q11','fr','tests automatisés pytest','p29',['p21']),
 ('q12','en','pytest automated API testing','p20',['p21']),
 ('q13','en','React UI implementation','p23',['p22']),
 ('q14','fr','utilisation Git pour revue du code','p16',['p24']),
 ('q15','en','Kubernetes deployment','p18',['p19']),
 ('q16','fr','analyse de données avec Python','p15',['p14']),
 ('q17','en','inventory stock reconciliation','p27',['p10']),
]

def build():
    documents=[f'synthetic_doc_{i:03d}' for i in range(1,len(PASSAGES)+1)]
    passage_rows=[{'id':pid,'organization_id':'fictional_tenant_a',
                   'document_id':doc,'page_number':1,'start_offset':0,'text':text}
                  for (pid,text),doc in zip(PASSAGES,documents)]
    passage_rows.append({'id':'foreign01','organization_id':'fictional_tenant_b',
       'document_id':'foreign_doc','page_number':1,'start_offset':0,
       'text':'Built Angular TypeScript apps. CONTACT EXAMPLE RESTRICTED.'})
    query_rows=[{'id':qid,'language':lang,'requirement':req,
        'organization_id':'fictional_tenant_a','authorized_documents':documents,
        'relevant_passage_ids':[correct],'hard_negative_passage_ids':negative}
        for qid,lang,req,correct,negative in CASES]
    return {'data_notice':'Entirely fictional, manually specified labels; cannot validate real recruiting models.',
            'passages':passage_rows,'queries':query_rows}

if __name__=='__main__':
    out=Path(__file__).resolve().parents[1]/'datasets'/'synthetic'/'hybrid-retrieval-v10.json'
    out.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out)
