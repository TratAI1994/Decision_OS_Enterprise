import pytest
from backend.readiness_engine import (CONTROLS, SCHEMA, canonical, evaluate, from_trust_response, sample_manifest, validate_manifest)

def test_fail_closed_empty():
 r=evaluate(sample_manifest('D1'));assert not r['certified'];assert r['summary']['NOT_TESTED']==len(CONTROLS)

def test_untrusted_claim_never_passes():
 m=sample_manifest('D1');m['controls']['ci']={'status':'PASS','evidence_ref':'jenkins-run-123','verified_by':'alice'}
 r=evaluate(m);assert r['summary']['PASS']==0
 assert next(x for x in r['findings'] if x['control']=='ci')['status']=='NOT_TESTED'

def test_authenticated_verifier_limited_to_provided_identity():
 m=sample_manifest('D1');m['controls']['ci']={'status':'PASS','evidence_ref':'jenkins-run-123','verified_by':'alice'}
 r=evaluate(m,authenticated_verifiers={'alice'});assert r['summary']['PASS']==0
 r=evaluate(m,authenticated_verifiers={'alice'},validated_evidence_refs={'jenkins-run-123'});assert r['summary']['PASS']==1;assert not r['certified']

def test_all_claims_require_authenticated_verifier():
 m=sample_manifest('D1')
 for key,_ in CONTROLS:m['controls'][key]={'status':'PASS','evidence_ref':'independent-proof-456','verified_by':'alice'}
 assert not evaluate(m)['certified']
 assert not evaluate(m,authenticated_verifiers={'alice'})['certified']
 assert evaluate(m,authenticated_verifiers={'alice'},validated_evidence_refs={'independent-proof-456'})['certified'] # Only when actual trusted source validation exists

def test_missing_pass_reference_fails():
 m=sample_manifest('D1');m['controls']['ci']={'status':'PASS','verified_by':'alice','evidence_ref':'x'}
 with pytest.raises(ValueError):validate_manifest(m)

def test_unknown_control_fails():
 m=sample_manifest('D1');m['controls']['invented']={'status':'PASS'}
 with pytest.raises(ValueError):validate_manifest(m)

def test_schema_rejected():
 m=sample_manifest('D1');m['schema']='incorrect'
 with pytest.raises(ValueError):evaluate(m)

def test_upstream_nonboolean_is_not_pass():
 m=from_trust_response({'decision_id':'D9','checks':{'approval_time_atomic_business_record':'NOT_IMPLEMENTED','production_devsecops_deployment':True}})
 r=evaluate(m);assert not r['certified'];assert r['summary']['NOT_IMPLEMENTED']==1;assert r['summary']['PASS']==0

def test_report_hash_stable():
 assert evaluate(sample_manifest('D1'))['sha256']==evaluate(sample_manifest('D1'))['sha256']

def test_json_nan_is_rejected():
 with pytest.raises(ValueError):canonical({'amount':float('nan')})
