"""Optional local semantic retrieval. Vector similarity is a SEARCH HINT, never proof.

DB IDs and page offsets only are placed in Qdrant, no names/CV text in payload.
The caller MUST recheck tenant access against MySQL; Qdrant payload is not authorization.
"""
from hashlib import sha256
from uuid import uuid5, NAMESPACE_URL
from typing import Protocol

class Embedder(Protocol):
    def encode(self, texts: list[str]): ...


def semantic_collection(model_name: str) -> str:
    return 'tr_pages_' + sha256(model_name.encode('utf-8')).hexdigest()[:14]


def chunks(text: str, max_length: int = 750) -> list[tuple[int, int, str]]:
    """Bounded deterministic windows over source; offsets always reference source text."""
    if not text.strip(): return []
    result=[]
    start=0
    while start<len(text):
        end=min(len(text), start+max_length)
        if end<len(text):
            boundary=max(text.rfind('\n',start+max(1,max_length//2),end),
                         text.rfind('. ',start+max(1,max_length//2),end))
            if boundary>start: end=boundary+1
        piece=text[start:end]
        if piece.strip(): result.append((start,end,piece))
        start=end
    return result


def index_pages(client, embedder: Embedder, *, model_name: str, dimension: int,
                organization_id: str, document_id: str, pages: list[tuple[str,str]]):
    """Upsert deterministic IDs; caller provides authoritative DB-scoped pages.

    This does NOT store any talent/score/skill interpretation.
    """
    from qdrant_client import models
    collection=semantic_collection(model_name)
    if not client.collection_exists(collection):
        client.create_collection(collection, vectors_config=models.VectorParams(
            size=dimension, distance=models.Distance.COSINE))
        client.create_payload_index(collection, 'organization_id', models.PayloadSchemaType.KEYWORD)
    # Re-index is replaced, rather than keeping old vectors from modified pages.
    client.delete(collection, models.FilterSelector(filter=models.Filter(
        must=[models.FieldCondition(key='organization_id',match=models.MatchValue(value=organization_id)),
              models.FieldCondition(key='document_id',match=models.MatchValue(value=document_id))])))
    passages=[(page_id,s,e,text) for page_id,page_text in pages
              for s,e,text in chunks(page_text)]
    if not passages: return 0
    batch_size=16
    for offset in range(0,len(passages),batch_size):
        block=passages[offset:offset+batch_size]
        vectors=embedder.encode([b[3] for b in block])
        points=[]
        for (page_id,start,end,content), vector in zip(block,vectors,strict=True):
            vector=[float(v) for v in vector]
            if len(vector)!=dimension: raise ValueError('EMBEDDING_DIMENSION_MISMATCH')
            point_id=str(uuid5(NAMESPACE_URL, '/'.join([organization_id,document_id,page_id,str(start),model_name])))
            points.append(models.PointStruct(id=point_id, vector=vector, payload={
                'organization_id':organization_id, 'document_id':document_id,
                'page_id':page_id, 'start':start, 'end':end, 'model_name':model_name}))
        client.upsert(collection, points, wait=True)
    return len(passages)


def search_passages(client, embedder: Embedder, *, model_name: str,
                    organization_id: str, query: str, limit: int = 10):
    """Mandatory tenant filter AND external authorization required before returning excerpts."""
    from qdrant_client import models
    if not query.strip() or len(query)>250: raise ValueError('INVALID_SEARCH_QUERY')
    collection=semantic_collection(model_name)
    if not client.collection_exists(collection): return []
    vector=[float(v) for v in embedder.encode([query])[0]]
    results=client.query_points(collection, query=vector,
         query_filter=models.Filter(must=[models.FieldCondition(
             key='organization_id', match=models.MatchValue(value=organization_id))]),
         limit=max(1,min(limit,25)),with_payload=True,with_vectors=False).points
    return [{'document_id':p.payload.get('document_id'),'page_id':p.payload.get('page_id'),
             'start':p.payload.get('start'),'end':p.payload.get('end'),
             'similarity':round(float(p.score),5)} for p in results if p.payload]


class LocalSentenceEmbedder:
    """Loads model ONLY when requested (opt-in). Models run locally; download first use."""
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model=SentenceTransformer(model_name, device='cpu', trust_remote_code=False)
        self.dimension=int(self.model.get_sentence_embedding_dimension())
    def encode(self,texts):
        return self.model.encode(texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False)
