from app.core.database import SessionLocal
from app.ml.terminology import seed_glossary

if __name__ == '__main__':
    with SessionLocal() as session:
        seed_glossary(session)
        print('Référentiel local de départ installé (non ESCO).')
