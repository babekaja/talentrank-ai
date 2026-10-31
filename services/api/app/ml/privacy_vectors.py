"""Remove every matching page-vector from ALL TalentRank collections, including old model versions."""
from qdrant_client import models


def delete_document_vectors(client, *, organization_id: str, document_id: str) -> int:
    collections = [x.name for x in client.get_collections().collections if x.name.startswith('tr_pages_')]
    for name in collections:
        where = models.Filter(must=[
            models.FieldCondition(key='organization_id', match=models.MatchValue(value=organization_id)),
            models.FieldCondition(key='document_id', match=models.MatchValue(value=document_id)),
        ])
        client.delete(name, models.FilterSelector(filter=where), wait=True)
        # Qdrant can acknowledge a request yet retain matching points if an
        # old index is inconsistent. Verify before erasing the SQL reference.
        remaining = client.count(name, count_filter=where, exact=True).count
        if remaining:
            raise RuntimeError('QDRANT_DELETION_NOT_CONFIRMED')
    return len(collections)
