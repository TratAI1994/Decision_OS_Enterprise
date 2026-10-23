import json,os
from fastapi.testclient import TestClient
from backend.api import app,configure

def test_funding_decisions_scoped_by_initiative_and_tenant():
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({'a':{'user':'lead-a','tenant':'A','role':'lead'},'b':{'user':'lead-b','tenant':'B','role':'lead'}})
    configure('sqlite:///:memory:')
    client=TestClient(app)
    def call(method,path,key='a',**kw):return client.request(method,path,headers={'Authorization':f'Bearer {key}'},**kw)
    a=call('POST','/v1/initiatives',json={'name':'Claims Triage Copilot','owner':'Claims Director'}).json()['id']
    other=call('POST','/v1/initiatives',json={'name':'Different Initiative','owner':'Director'}).json()['id']
    b=call('POST','/v1/initiatives',key='b',json={'name':'Outside Tenant','owner':'Director'}).json()['id']
    def decision(i,title,key='a'):
        r=call('POST','/v1/intelligence/decisions',key=key,json={'initiative_id':i,'title':title,'option_chosen':'approve','rationale':'approve based on value case','alternatives':[],'assumptions':[],'evidence_refs':[]})
        assert r.status_code==201,r.text
        return r.json()['id']
    expected=decision(a,'Expand AI Knowledge to finance function')
    decision(other,'Other board decision')
    decision(b,'Private board decision','b')
    res=call('GET',f'/v1/initiatives/{a}/funding-decisions')
    assert res.status_code==200,res.text
    assert len(res.json())==1 and res.json()[0]['id']==expected
    assert res.json()[0]['title']=='Expand AI Knowledge to finance function'
    assert call('GET',f'/v1/initiatives/{a}/funding-decisions',key='b').status_code==404
    assert call('GET',f'/v1/initiatives/{b}/funding-decisions').status_code==404
    assert call('GET','/v1/initiatives/bad/funding-decisions').status_code==404
