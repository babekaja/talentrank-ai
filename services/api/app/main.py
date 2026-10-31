from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.auth import router as auth_router
from app.api.v1.team import router as team_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.candidates import router as candidates_router
from app.api.v1.audit import router as audit_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.documents import router as documents_router
from app.api.v1.nlp import router as nlp_router
from app.api.v1.semantic import router as semantic_router
from app.api.v1.matching import router as matching_router
from app.api.v1.insights import router as insights_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.evaluator import router as evaluator_router
from app.api.v1.training import router as training_router
from app.api.v1.africa import router as africa_router
from app.api.v1.candidate_portal import router as portal_router
from app.core.config import get_settings
from app.core.database import get_db
from fastapi import Depends

settings = get_settings()
app = FastAPI(title='TalentRank AI : API', version='0.27.0',
              description='Plateforme TalentRank AI : NLP non génératif, preuves, contrôle humain et accès isolés par entreprise. Les modèles expérimentaux ne prennent aucune décision de recrutement.')


@app.exception_handler(RequestValidationError)
async def validation_error_without_inputs(request, error: RequestValidationError):
    # Les valeurs saisies peuvent contenir un mot de passe ou des données privées.
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': list(item['loc']), 'msg': item['msg'], 'type': item['type']}
        for item in error.errors()
    ]})


app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'])
app.include_router(auth_router, prefix='/api/v1', tags=['Identité'])
app.include_router(team_router, prefix='/api/v1', tags=['Équipe et invitations'])
app.include_router(jobs_router, prefix='/api/v1', tags=['Offres'])
app.include_router(campaigns_router, prefix='/api/v1', tags=['Campagnes'])
app.include_router(candidates_router, prefix='/api/v1', tags=['Candidatures'])
app.include_router(audit_router, prefix='/api/v1', tags=['Audit'])
app.include_router(uploads_router, prefix='/api/v1', tags=['Importation'])
app.include_router(documents_router, prefix='/api/v1', tags=['Documents'])
app.include_router(nlp_router, prefix='/api/v1', tags=['NLP et preuves'])
app.include_router(semantic_router, prefix='/api/v1', tags=['Recherche sémantique'])
app.include_router(matching_router, prefix='/api/v1', tags=['Matching explicable'])
app.include_router(insights_router, prefix='/api/v1', tags=['Analytique, qualité et rapports'])
app.include_router(evaluator_router, prefix='/api/v1', tags=['Évaluations humaines'])
app.include_router(training_router, prefix='/api/v1', tags=['Formations vérifiables'])
app.include_router(africa_router, prefix='/api/v1', tags=['Africa Skills Intelligence'])
app.include_router(portal_router, prefix='/api/v1', tags=['Espace candidat : consentement'])
app.include_router(privacy_router, prefix='/api/v1', tags=['Confidentialité et rétention'])


@app.get('/health/live', tags=['Santé'])
def liveness():
    return {'status': 'alive', 'service': 'talentrank-api'}


@app.get('/health/ready', tags=['Santé'])
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(503, 'Base de données indisponible') from None
    return {'status': 'ready'}
