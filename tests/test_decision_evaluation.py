from backend.decision_evaluation import (
    WEIGHTS,
    content_hash,
    outcome_language,
    score_answers,
)


def complete():
    return {k:{'state':'verified','evidence_ref':'EVIDENCE-123','explanation':'Source has been reviewed'} for k in WEIGHTS}

def test_complete_score_is_reproducible():
    a=complete()
    assert score_answers(a)['score']==100
    assert score_answers(a)==score_answers(dict(reversed(list(a.items()))))

def test_missing_or_provisional_withheld():
    for state in ('missing','provisional'):
        a=complete();a['risk']['state']=state
        assert score_answers(a)['score'] is None

def test_verified_needs_reference():
    a=complete();a['economics']['evidence_ref']=''
    assert score_answers(a)['score'] is None

def test_na_requires_justification():
    a=complete();a['counterfactual']['state']='not_applicable';a['counterfactual']['explanation']='n/a'
    assert score_answers(a)['score'] is None
    a['counterfactual']['explanation']='Not applicable because no intervention exists in this specific decision.'
    assert score_answers(a)['score']==100

def test_no_causality_from_correlation():
    for label in ('correlational','estimated','unknown'):
        assert 'not established' in outcome_language(label)

def test_canonical_hash_stable():
    assert content_hash({'a':1,'b':2})==content_hash({'b':2,'a':1})

def test_api_draft_tenant_identity_and_lock_gates():
    import json
    import os

    from fastapi.testclient import TestClient

    from backend.api import app, configure
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({
        'lead':{'user':'lead','tenant':'A','role':'lead'},
        'reviewer':{'user':'reviewer','tenant':'A','role':'reviewer'},
        'other':{'user':'other','tenant':'B','role':'lead'}})
    configure('sqlite:///:memory:')
    c=TestClient(app)
    def q(method,path,who='lead',**kwargs):return c.request(method,path,headers={'Authorization':'Bearer '+who},**kwargs)
    i=q('POST','/v1/initiatives',json={'name':'Demo initiative','owner':'Lead'}).json()['id']
    d=q('POST','/v1/intelligence/decisions',json={'initiative_id':i,'title':'Pilot decision','option_chosen':'Pilot','rationale':'Run controlled pilot'}).json()['id']
    payload={'decision_id':d,'request_id':'unique-evaluation-123','answers':complete()}
    first=q('POST','/v1/decision-evaluation/draft',json=payload)
    assert first.status_code==201,first.text
    rec=first.json()
    assert q('POST','/v1/decision-evaluation/draft',json=payload).json()['id']==rec['id']
    assert q('GET',f'/v1/decision-evaluation/decisions/{d}',who='other').status_code==404
    assert q('GET',f'/v1/decision-evaluation/decisions/{d}').json()[0]['status']=='draft'
    lock={'expected_status':'draft','confirmation':'I have independently reviewed the evidence and accept the limitations.'}
    assert q('POST',f"/v1/decision-evaluation/{rec['id']}/lock",json=lock).status_code==403
    # Independent reviewer cannot manufacture a lock without approved packet.
    denied=q('POST',f"/v1/decision-evaluation/{rec['id']}/lock",who='reviewer',json=lock)
    assert denied.status_code==409,denied.text
    assert q('GET',f'/v1/decision-evaluation/decisions/{d}').json()[0]['status']=='draft'
