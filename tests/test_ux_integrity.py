"""R3 UX/backend integrity regression: tenant FKs, request replay, source-aware board briefs."""
import os,json
from fastapi.testclient import TestClient
from backend.api import app, configure

def test_reference_and_idempotency_boundary():
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({
      'a':{'user':'a','role':'lead','tenant':'tenant-A'},
      'b':{'user':'b','role':'lead','tenant':'tenant-B'}})
    configure('sqlite:///:memory:')
    c=TestClient(app)
    def req(method,path,token='a',**kw):
        return c.request(method,path,headers={'Authorization':'Bearer '+token},**kw)
    ia=req('POST','/v1/initiatives',json={'name':'Tenant A initiative','owner':'Owner A','description':'demo'}).json()['id']
    ib=req('POST','/v1/initiatives',token='b',json={'name':'Tenant B initiative','owner':'Owner B','description':'demo'}).json()['id']
    base={'kind':'risk','name':'Risk Assessment','owner':'Owner A','payload':{'initiative_id':ia,'likelihood':.25,'impact_usd':300},'request_id':'stable_test_request_123'}
    assert req('POST','/v1/intelligence/records',json={**base,'payload':{'initiative_id':ib}}).status_code==404
    a=req('POST','/v1/intelligence/records',json=base)
    assert a.status_code==201,a.text
    b=req('POST','/v1/intelligence/records',json=base)
    assert b.status_code in (200,201) and a.json()['id']==b.json()['id']
    assert len(req('GET','/v1/intelligence/records?kind=risk').json())==1
    assert len(req('GET','/v1/intelligence/records?kind=risk',token='b').json())==0
    assert req('PUT',f"/v1/intelligence/records/{a.json()['id']}",json={'expected_version':1,'payload':{'initiative_id':ib}}).status_code==404
    brief=req('POST','/v1/intelligence/executive-narrative',json={'audience':'board'})
    assert brief.status_code==200,brief.text
    report=brief.json()
    assert report['finance_reconciled_count']==0 and report['finance_reconciled_value'] is None
    assert 'finance-reconciled' in report['narrative']
