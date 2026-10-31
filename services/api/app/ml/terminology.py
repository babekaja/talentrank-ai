"""Small LOCAL, HUMAN-CURATED starter glossary. Not claimed to be ESCO.

Never treat a related term as an equivalent term (FastAPI != Python, Docker != Kubernetes).
"""
CURATED_SKILLS = [
    ('angular', 'Angular', 'Angular', ['angular', 'angular framework']),
    ('angular_material', 'Angular Material', 'Angular Material',
        ['angular material', 'material angular']),
    ('typescript', 'TypeScript', 'TypeScript', ['typescript']),
    ('javascript', 'JavaScript', 'JavaScript', ['javascript', 'js']),
    ('html', 'HTML', 'HTML', ['html', 'html5']),
    ('css', 'CSS', 'CSS', ['css', 'css3', 'cascading style sheets']),
    ('rxjs', 'RxJS', 'RxJS', ['rxjs', 'reactive extensions for javascript']),
    ('figma', 'Figma', 'Figma', ['figma']),
    ('web_accessibility', 'Accessibilité numérique', 'Web accessibility',
        ['accessibilité web', 'accessibilite web', 'accessibilité numérique',
         'accessibilite numerique', 'web accessibility', 'wcag']),
    ('python', 'Python', 'Python', ['python']),
    ('fastapi', 'FastAPI', 'FastAPI', ['fastapi']),
    ('pytorch', 'PyTorch', 'PyTorch', ['pytorch', 'torch']),
    ('nlp', 'Traitement automatique du langage', 'Natural language processing',
        ['nlp', 'natural language processing', 'traitement automatique du langage',
         'traitement du langage naturel', 'taln']),
    ('transformers', 'Architectures Transformers', 'Transformer architectures',
        ['transformers', 'transformer', 'hugging face transformers', 'huggingface transformers']),
    ('mlops', 'MLOps', 'MLOps', ['mlops', 'machine learning operations']),
    ('model_evaluation', 'Évaluation des modèles de Machine Learning', 'Machine learning model evaluation',
        ['évaluation des modèles', 'evaluation des modeles', 'model evaluation',
         'machine learning metrics', 'métriques machine learning']),
    ('spacy', 'spaCy', 'spaCy', ['spacy']),
    ('embeddings_semantic_search', 'Embeddings et recherche sémantique', 'Embeddings and semantic search',
        ['embeddings', 'embedding', 'recherche sémantique', 'recherche semantique',
         'semantic search', 'vector search']),
    ('document_classification', 'Classification de documents', 'Document classification',
        ['classification de documents', 'classification documentaire', 'document classification']),
    ('onnx', 'ONNX', 'ONNX', ['onnx', 'open neural network exchange']),
    ('scikit_learn', 'scikit-learn', 'scikit-learn',
        ['scikit-learn', 'scikit learn', 'sklearn']),
    ('mysql', 'MySQL', 'MySQL', ['mysql']),
    ('postgresql', 'PostgreSQL', 'PostgreSQL', ['postgresql', 'postgres']),
    ('rest_api', 'Développement d’API REST', 'REST API development',
        ['développement api rest', 'developpement api rest', 'développement d’api rest',
         'developpement d api rest', 'rest api development', 'conception d’api rest',
         'conception d api rest', 'api rest', 'restful api', 'rest services']),
    ('relational_databases', 'Bases de données relationnelles', 'Relational databases',
        ['bases de données relationnelles', 'bases de donnees relationnelles',
         'base de données relationnelle', 'relational databases']),
    ('git', 'Git', 'Git', ['git', 'git version control']),
    ('docker', 'Docker', 'Docker', ['docker']),
    ('automated_testing', 'Tests logiciels automatisés', 'Automated software testing',
        ['tests automatisés', 'tests automatises', 'automated testing', 'tests logiciels automatisés']),
    ('inventory_management', 'Gestion des stocks', 'Inventory management',
        ['gestion des stocks', 'inventory management']),
    ('supply_chain', 'Gestion de la chaîne d’approvisionnement', 'Supply chain management',
        ['supply chain management', 'gestion de la chaîne d’approvisionnement',
         'gestion de la chaine d approvisionnement']),
    ('kotlin', 'Kotlin', 'Kotlin', ['kotlin']),
    ('java', 'Java', 'Java', ['java']),
    ('linux', 'Linux', 'Linux', ['linux']),
    ('excel', 'Excel', 'Excel', ['microsoft excel', 'excel']),
]


def seed_glossary(db):
    from sqlalchemy import select
    from app.models import Skill, SkillAlias
    for code, fr, en, variants in CURATED_SKILLS:
        skill = db.scalar(select(Skill).where(Skill.code == code))
        if skill is None:
            skill = Skill(code=code, label_fr=fr, label_en=en, taxonomy='curated-local', version='local-1')
            db.add(skill)
            db.flush()
        seen = set()
        for alias in variants:
            from app.ml.recognition import normalize
            value = normalize(alias)
            if value in seen:
                continue
            seen.add(value)
            exists = db.scalar(select(SkillAlias).where(
                SkillAlias.skill_id == skill.id, SkillAlias.normalized_alias == value))
            if not exists:
                db.add(SkillAlias(skill_id=skill.id, normalized_alias=value,
                                  provenance='curated-local', verified=True))
    db.commit()
