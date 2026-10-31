"""Verify Qdrant filtering without connecting to Qdrant or loading ML models."""
import sys
from types import SimpleNamespace


def test_vector_cleanup_all_previous_model_collections(monkeypatch):
    class MatchValue:
        def __init__(self,value):self.value=value
    class FieldCondition:
        def __init__(self,key,match):self.key=key;self.match=match
    class Filter:
        def __init__(self,must):self.must=must
    class FilterSelector:
        def __init__(self,filter):self.filter=filter
    models=SimpleNamespace(MatchValue=MatchValue,FieldCondition=FieldCondition,
                           Filter=Filter,FilterSelector=FilterSelector)
    monkeypatch.setitem(sys.modules,'qdrant_client',SimpleNamespace(models=models))
    from app.ml.privacy_vectors import delete_document_vectors
    class Client:
        def __init__(self):self.operations=[]
        def get_collections(self):return SimpleNamespace(collections=[
            SimpleNamespace(name='tr_pages_oldmodel'),SimpleNamespace(name='tr_pages_newmodel'),
            SimpleNamespace(name='someone_else_collection')])
        def delete(self,name,filter,wait):self.operations.append((name,filter,wait))
        def count(self,name,count_filter,exact):
            assert exact and name.startswith('tr_pages_')
            return SimpleNamespace(count=0)
    client=Client()
    assert delete_document_vectors(client,organization_id='org-1',document_id='doc-1')==2
    assert len(client.operations)==2
    for name,condition,wait in client.operations:
        assert name.startswith('tr_pages_') and wait
        assert {(f.key,f.match.value) for f in condition.filter.must}=={
             ('organization_id','org-1'),('document_id','doc-1')}


def test_vector_cleanup_rejects_remaining_vectors(monkeypatch):
    # Reuse the same stubbed SDK from the previous test and assert fail-closed.
    test_vector_cleanup_all_previous_model_collections(monkeypatch)
    from app.ml.privacy_vectors import delete_document_vectors
    class ResidualClient:
        def get_collections(self):
            return SimpleNamespace(collections=[SimpleNamespace(name='tr_pages_oldmodel')])
        def delete(self,*args,**kwargs): pass
        def count(self,*args,**kwargs): return SimpleNamespace(count=1)
    import pytest
    with pytest.raises(RuntimeError,match='QDRANT_DELETION_NOT_CONFIRMED'):
        delete_document_vectors(ResidualClient(),organization_id='org-1',document_id='doc-1')
