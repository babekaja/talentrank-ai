"""Internal, non-generative model service. Never published on the host network.

Only the trusted API/worker may call it, over the internal Docker network.
"""
from functools import lru_cache
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.ml.vectors import LocalSentenceEmbedder, index_pages, search_passages
from app.ml.skill_rank import rank_labels

app=FastAPI(title='TalentRank internal semantic service',docs_url=None,redoc_url=None,openapi_url=None)

class PageIn(BaseModel):
    id: str = Field(max_length=36)
    text: str = Field(max_length=250000)
class IndexIn(BaseModel):
    organization_id: str = Field(max_length=36)
    document_id: str = Field(max_length=36)
    pages: list[PageIn] = Field(max_length=200)
class SearchIn(BaseModel):
    organization_id: str = Field(max_length=36)
    query: str = Field(min_length=2,max_length=250)
    limit: int = Field(default=10,ge=1,le=25)

@lru_cache(maxsize=1)
def backend():
    from qdrant_client import QdrantClient
    settings=get_settings()
    model=LocalSentenceEmbedder(settings.embedding_model)
    return QdrantClient(url=settings.qdrant_url,timeout=30),model

def verify(token: str | None):
    from secrets import compare_digest
    expected=get_settings().ml_service_token
    if not expected or expected.startswith('CHANGE_') or not token or not compare_digest(token,expected):
        raise HTTPException(403,'Service interne non autorisé')

@app.get('/live')
def live(): return {'status':'alive'}

@app.post('/private/index')
def index(body:IndexIn,x_internal_token:str|None=Header(None)):
    verify(x_internal_token)
    client,embedder=backend()
    count=index_pages(client,embedder,model_name=get_settings().embedding_model,
                      dimension=embedder.dimension,organization_id=body.organization_id,
                      document_id=body.document_id,pages=[(p.id,p.text) for p in body.pages])
    return {'indexed_passages':count,'model':get_settings().embedding_model}

@app.post('/private/search')
def search(body:SearchIn,x_internal_token:str|None=Header(None)):
    verify(x_internal_token)
    client,embedder=backend()
    results=search_passages(client,embedder,model_name=get_settings().embedding_model,
                            organization_id=body.organization_id,query=body.query,limit=body.limit)
    return {'items':results,'model':get_settings().embedding_model,
            'disclaimer':'Similarité documentaire uniquement; aucune compétence prouvée.'}


class LabelIn(BaseModel):
    skill_id: str = Field(min_length=1, max_length=36)
    label: str = Field(min_length=2, max_length=180)

class RankIn(BaseModel):
    query: str = Field(min_length=2, max_length=250)
    labels: list[LabelIn] = Field(min_length=1, max_length=120)
    limit: int = Field(default=8, ge=1, le=20)

@app.post('/private/rank-skills')
def rank_skills(body: RankIn, x_internal_token: str | None = Header(None)):
    verify(x_internal_token)
    _client, embedder = backend()
    items = rank_labels(embedder, body.query,
        [(label.skill_id, label.label) for label in body.labels], limit=body.limit)
    return {'items': items, 'model': get_settings().embedding_model,
            'warning': 'Pistes de recherche seulement : aucune équivalence établie.'}


class DeleteIn(BaseModel):
    organization_id: str = Field(max_length=36)
    document_id: str = Field(max_length=36)

@app.post('/private/delete')
def delete_vectors(body:DeleteIn,x_internal_token:str|None=Header(None)):
    verify(x_internal_token)
    # Deletion must not trigger heavyweight embedding model loading.
    from qdrant_client import QdrantClient
    from app.ml.privacy_vectors import delete_document_vectors
    client=QdrantClient(url=get_settings().qdrant_url,timeout=30)
    count=delete_document_vectors(client, organization_id=body.organization_id,document_id=body.document_id)
    return {'collections_checked':count}
