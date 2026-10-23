import os,json
from fastapi.testclient import TestClient
from backend.api import app,configure

def test_r5_trust_lineage_isolation_and_reviews():
 os.environ['DECISION_OS_IDENTITIES']=json.dumps({'a':{'user':'lead-a','tenant':'A','role':'lead'},'b':{'user':'lead-b','tenant':'B','role':'lead'},'r':{'user':'reviewer-a','tenant':'A','role':'reviewer'}})
 configure('sqlite:///:memory:')
 c=TestClient(app)
 def r(method,path,key='a',**kwargs):return c.request(method,path,headers={'Authorization':'Bearer '+key},**kwargs)
 ia=r('POST','/v1/initiatives',json={'name':'AI Claims','owner':'Risk Director','description':''}).json()['id']
 ib=r('POST','/v1/initiatives',key='b',json={'name':'Private AI','owner':'Risk Director','description':''}).json()['id']
 def decision(i,k):
  res=r('POST','/v1/intelligence/decisions',key=k,json={'initiative_id':i,'title':'Fund pilot','option_chosen':'test','rationale':'pilot to validate economic hypotheses','assumptions':[],'alternatives':[],'evidence_refs':[]})
  assert res.status_code==201,res.text
  return res.json()['id']
 da=decision(ia,'a');db=decision(ib,'b')
 payload={'initiative_id':ia,'decision_id':db,'title':'Claims model','ai_role':'deployer','geography':'EU','intended_use':'Draft recommended claim handling actions for review','classification':'review_required','owner':'Lead Risk','assessment_source':'test-risk-report','risk_factors':{'sensitive_data':True}}
 assert r('POST','/v1/trust/assessments',json=payload).status_code==422
 created=r('POST','/v1/trust/assessments',json={**payload,'decision_id':da})
 assert created.status_code==201,created.text
 aid=created.json()['id']
 assert r('GET',f'/v1/trust/assessments/{aid}',key='b').status_code==404
 assert r('GET','/v1/trust/assessments',key='b').json()==[]
 assert r('POST',f'/v1/trust/assessments/{aid}/review',json={'expected_version':1,'decision':'accept_for_review','note':'Legal scope reviewed'}).status_code==403
 control=r('POST',f'/v1/trust/assessments/{aid}/controls',json={'framework':'NIST_AI_RMF','control_id':'MEASURE','evidence_reference':'audit://doc-1','evidence_quality':'self_reported'})
 assert control.status_code==201,control.text
 assert r('POST',f"/v1/trust/controls/{control.json()['id']}/verify",key='r').status_code==200
 reviewed=r('POST',f'/v1/trust/assessments/{aid}/review',key='r',json={'expected_version':1,'decision':'accept_for_review','note':'Applies provisionally; further testing required'})
 assert reviewed.status_code==200,reviewed.text
 assert reviewed.json()['certified_compliance'] is False
 assert r('POST',f'/v1/trust/assessments/{aid}/review',key='r',json={'expected_version':1,'decision':'accept_for_review','note':'another'}).status_code==409
 one={'format':'pyrit_normalized_v1','findings':[{'source_tool':'pyrit','source_run_id':'run1','source_finding_id':'f1','category':'prompt_injection','severity':'high','title':'Observed tool boundary bypass','evidence_reference':'artifact://finding/one','observed_result':'Tool-call attempt reached mock executor','remediation':'Add enforced action scope and retest'}]}
 created=r('POST',f'/v1/trust/assessments/{aid}/findings/import',json=one)
 assert created.status_code==201,created.text
 fid=created.json()['created_ids'][0]
 repeated=r('POST',f'/v1/trust/assessments/{aid}/findings/import',json=one)
 assert repeated.status_code==201 and repeated.json()['duplicate_ids']==[fid]
 assert r('GET','/v1/trust/findings',key='b').json()==[]
 detail=r('GET',f'/v1/trust/assessments/{aid}').json()
 assert detail['release_advisory']['high_or_critical_unresolved']==1
 assert detail['release_advisory']['eligible_for_automatic_release'] is False
 assert detail['decision_id']==da
 assert r('POST',f'/v1/trust/findings/{fid}/review',json={'expected_version':1,'disposition':'triaged','note':'risk reviewed'}).status_code==403
 approved=r('POST',f'/v1/trust/findings/{fid}/review',key='r',json={'expected_version':1,'disposition':'remediated_pending_retest','note':'fix awaiting independent test'})
 assert approved.status_code==200,approved.text
 assert approved.json()['approved_for_release'] is False
 assert r('POST',f'/v1/trust/findings/{fid}/review',key='r',json={'expected_version':1,'disposition':'false_positive','note':'conflict'}).status_code==409
 assert r('GET','/v1/trust/summary').json()['findings']==1
