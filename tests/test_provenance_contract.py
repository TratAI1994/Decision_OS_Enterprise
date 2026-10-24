import copy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import pytest
from backend.provenance_contract import SourceIdentity,ProvenanceError,prepare_evidence,verify_envelope
DATA=b'{"build":"1042","passed":true}'
VALID={'tenant_id':'tenant-a','source_system':'jenkins','source_record':'build-1042','captured_at':'2026-10-22T12:00:00Z','content_sha256':sha256(DATA).hexdigest(),'schema_version':'1.0'}
SOURCE=SourceIdentity('jenkins','jenkins-prod-collector',True,'mtls')
NOW=datetime(2026,10,23,tzinfo=timezone.utc)
def make(e=None,c=DATA,s=SOURCE,t='tenant-a'):
 return prepare_evidence(e or VALID,c,t,s,now=NOW)
def test_verified_digest():
 x=make();assert verify_envelope(x);assert x['verification_status']=='COLLECTOR_AUTHENTICATED_CONTENT_MATCHED'
def test_tamper():
 x=make();x['source_record']='build-999';assert not verify_envelope(x)
def test_tenant():
 with pytest.raises(ProvenanceError,match='tenant'): make(t='tenant-b')
def test_untrusted_collector():
 with pytest.raises(ProvenanceError,match='authenticated'):make(s=SourceIdentity('jenkins','claimed',False,'mtls'))
def test_untrusted_method():
 with pytest.raises(ProvenanceError,match='authenticated'):make(s=SourceIdentity('jenkins','fake',True,'ui_toggle'))
def test_wrong_origin():
 with pytest.raises(ProvenanceError,match='principal'):make(s=SourceIdentity('sap','collector',True,'mtls'))
def test_digest_mismatch():
 with pytest.raises(ProvenanceError,match='digest'):make(c=b'changed')
def test_naive_timestamp():
 e=dict(VALID,captured_at='2026-10-22T12:00:00')
 with pytest.raises(ProvenanceError,match='timezone'):make(e)
def test_future_timestamp():
 e=dict(VALID,captured_at='2026-10-24T12:00:00Z')
 with pytest.raises(ProvenanceError,match='future'):make(e)
def test_unexpected_fields():
 e=dict(VALID,verification_status='VERIFIED')
 with pytest.raises(ProvenanceError,match='unexpected'):make(e)
def test_stable_digest():assert make()['envelope_sha256']==make()['envelope_sha256']
def test_missing():
 e=dict(VALID);del e['source_record']
 with pytest.raises(ProvenanceError,match='missing'):make(e)
def test_schema_version():
 with pytest.raises(ProvenanceError,match='version'):make(dict(VALID,schema_version='2.0'))
