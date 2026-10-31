"""Regression tests for secure retention and production fail-closed behavior."""
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.documents.storage import PrivateStorage
from app.core.config import Settings

class FakeMinio:
    def __init__(self, versions):
        self.versions=list(versions)
        self.removed=[]
        self.fail_on_listing=False
    def list_objects(self, bucket, prefix, recursive, include_version):
        if self.fail_on_listing:
            raise OSError('Storage unreachable')
        assert include_version and recursive
        return [SimpleNamespace(object_name=n, version_id=v) for n,v in self.versions if n.startswith(prefix)]
    def remove_object(self,bucket,key,version_id=None):
        self.removed.append((key,version_id))
        self.versions=[item for item in self.versions if item != (key,version_id)]

def test_purge_all_object_versions_and_delete_markers_without_other_keys():
    storage=PrivateStorage.__new__(PrivateStorage)
    storage.bucket='private';storage.client=FakeMinio([
        ('tenant/doc','v1'),('tenant/doc','v2'),('tenant/doc','marker'),('tenant/doc-copy','v3')])
    storage.purge('tenant/doc')
    assert storage.client.versions==[('tenant/doc-copy','v3')]
    assert len(storage.client.removed)==3

def test_purge_raises_when_storage_unavailable():
    storage=PrivateStorage.__new__(PrivateStorage)
    storage.bucket='private';storage.client=FakeMinio([('doc','v1')])
    storage.client.fail_on_listing=True
    with pytest.raises(OSError): storage.purge('doc')

def test_purge_empty_key_is_idempotent():
    storage=PrivateStorage.__new__(PrivateStorage)
    storage.bucket='private';storage.client=FakeMinio([])
    storage.purge('no-longer-present')
    assert storage.client.removed==[]

def test_production_portal_requires_smtp_and_https():
    base=dict(environment='production',jwt_secret='x'*64,
        database_url='mysql+pymysql://app@mysql/talentrank',
        cors_origins='https://jobs.example.org',refresh_cookie_secure=True,
        s3_secret_key='y'*40,malware_scan_enabled=True,candidate_portal_enabled=True)
    with pytest.raises(ValidationError):Settings(**base)
    with pytest.raises(ValidationError):Settings(**(base|{'candidate_portal_smtp_host':'mail.example.org',
            'candidate_portal_from_email':'noreply@example.org',
            'candidate_portal_base_url':'http://jobs.example.org'}))
    valid=Settings(**(base|{'candidate_portal_smtp_host':'mail.example.org',
            'candidate_portal_from_email':'noreply@example.org',
            'candidate_portal_base_url':'https://jobs.example.org'}))
    assert valid.candidate_portal_enabled


def test_release_gate_never_approves_missing_docker(monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
    import verify_release_v28
    monkeypatch.setattr(verify_release_v28,'diagnose', lambda:{'docker_cli_installed':False,'blocker':'DOCKER_CLI_NOT_INSTALLED'})
    report=verify_release_v28.run()
    assert report['production_approved'] is False
    assert report['blocker']=='DOCKER_CLI_NOT_INSTALLED'
    assert report['neural_accuracy']=='NOT_VALIDATED'



def test_neural_validation_rejects_shared_document_across_organizations():
    from app.ml.neural_eval_v24 import validate_corpus
    rows={'passages':[
      {'id':'p1','text':'Application Angular documentée','document_id':'shared-document',
       'organization_id':'tenant-a','split':'test'},
      {'id':'p2','text':'Projet Python documenté','document_id':'shared-document',
       'organization_id':'tenant-b','split':'test'}],
      'queries':[{'id':'q1','split':'test','language':'fr','family_id':'fa',
         'requirement':'Expérience Angular','organization_id':'tenant-a',
         'authorized_documents':['shared-document'],'relevant_passage_ids':['p1'],
         'annotator_ids':['a','b']}]}
    with pytest.raises(ValueError,match='DOCUMENT_TENANT_COLLISION'):
        validate_corpus(rows)
