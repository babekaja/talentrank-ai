"""Search semantic candidates, always reauthorize each result via SQL.

This API does not claim skill equivalence, generate scores or make decisions.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_role
from app.core.security import Principal
from app.core.config import get_settings
from app.models import CVDocument, DocumentPage
from app.ml.remote import ml_request
from app.services.audit import record
router=APIRouter()

class QueryIn(BaseModel):
    query: str = Field(min_length=2,max_length=250)
    limit: int = Field(default=10,ge=1,le=25)

@router.post('/semantic/search')
def search(body:QueryIn,actor:Principal=Depends(require_role('org_admin','recruiter')),
           db:Session=Depends(get_db)):
    if not get_settings().semantic_enabled:
        raise HTTPException(503,'Recherche sémantique non activée')
    try:
        remote=ml_request('/private/search',{'organization_id':actor.organization.id,
                                             'query':body.query,'limit':body.limit})
    except Exception:
        raise HTTPException(503,'Service sémantique indisponible') from None
    results=[]
    for hit in remote.get('items',[])[:body.limit]:
        # Qdrant cannot authorize access. Verify both the document and its page in MySQL.
        doc=db.scalar(select(CVDocument).where(CVDocument.id==hit.get('document_id'),
                         CVDocument.organization_id==actor.organization.id))
        if not doc or doc.status not in ('completed','needs_review'): continue
        page=db.scalar(select(DocumentPage).where(DocumentPage.id==hit.get('page_id'),
                       DocumentPage.document_id==doc.id))
        if not page: continue
        start,end=hit.get('start'),hit.get('end')
        if not isinstance(start,int) or not isinstance(end,int) or not (0<=start<end<=len(page.text)):
            continue
        results.append({'document_id':doc.id,'page_number':page.page_number,
                        'filename':doc.filename,'start_offset':start,'end_offset':end,
                        'excerpt':page.text[start:end], 'similarity':hit.get('similarity'),
                        'status':'retrieval_only'})
    record(db,actor,'semantic.search','organization',actor.organization.id,{'result_count':len(results)})
    db.commit()
    return {'items':results,'model':get_settings().embedding_model,
            'warning':'Un résultat de similarité n’est pas une preuve de maîtrise ou une équivalence.'}
