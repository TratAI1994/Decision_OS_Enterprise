from tools.r99_live_assurance import canonical,signed_request,perform,validate_db_guard,Result
from collections import defaultdict
import hashlib
import hmac
import pytest
KEY='72'*32

def transport_factory():
    seen=set()
    def send(_api,payload,headers):
        digest=hashlib.sha256(payload).hexdigest()
        msg=canonical({'timestamp':headers['X-Timestamp'],'nonce':headers['X-Nonce'],
            'tenant':headers['X-Tenant'],'source':headers['X-Source'],
            'source_record':headers['X-Source-Record'],'sha256':headers['X-Content-SHA256']})
        sig=hmac.new(bytes.fromhex(KEY),msg,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,headers['X-Signature']):return 401,{}
        if digest!=headers['X-Content-SHA256']:return 422,{}
        identity=headers['X-Nonce']
        if identity in seen:return 409,{}
        seen.add(identity)
        return 201,{'id':'abc','trust_state':'AUTHENTICATED_COLLECTOR_CONTENT_MATCHED',
                    'business_validated':False,'content_sha256':digest}
    return send

def test_signature_matches_r99_contract():
    payload,headers=signed_request(b'example',tenant='local-demo',source='jenkins',key_id='key-1',key_hex=KEY,source_record='build-1',timestamp='2026-10-23T00:00:00+00:00',nonce='nonce-1')
    expected=hmac.new(bytes.fromhex(KEY),canonical({'timestamp':headers['X-Timestamp'],'nonce':'nonce-1','tenant':'local-demo','source':'jenkins','source_record':'build-1','sha256':hashlib.sha256(b'example').hexdigest()}),hashlib.sha256).hexdigest()
    assert headers['X-Signature']==expected

def test_negative_controls():
    results,meta=perform('http://127.0.0.1:8001','local-demo','jenkins','key-1',KEY,transport=transport_factory(),concurrent=False)
    assert [r.result for r in results]==['PASS','PASS','PASS','PASS','NOT_TESTED']
    assert meta['evidence_id']=='abc'

def test_failure_prevents_false_negatives():
    results,_=perform('http://127.0.0.1:8001','local-demo','jenkins','key-1',KEY,transport=lambda *args:(404,{}))
    assert results[0].result=='FAIL'
    assert all(r.result=='NOT_TESTED' for r in results[1:])

@pytest.mark.parametrize('name', ['decision_os','production','main','prod','decision_os_test_backup'])
def test_disposable_guard_rejects_non_test_database(name):
    with pytest.raises(ValueError):validate_db_guard(name,'I_UNDERSTAND_TEST_DATABASE_ONLY')

@pytest.mark.parametrize('name',['decision_os_test','test_decision_os','decision_os_ci'])
def test_disposable_guard_permits_named_test_database(name):
    validate_db_guard(name,'I_UNDERSTAND_TEST_DATABASE_ONLY')

def test_guard_also_requires_ack():
    with pytest.raises(ValueError):validate_db_guard('decision_os_test','')

def test_short_key_rejected():
    with pytest.raises(ValueError):signed_request(b'x',tenant='local-demo',source='jenkins',key_id='key-1',key_hex='22',source_record='build-1')
