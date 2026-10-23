import os,json
from sqlalchemy import create_engine,text,inspect
from fastapi.testclient import TestClient
from backend.api import app,configure
from backend.migration_r511 import migrate
from ui.validation import errors_for_assessment,autofill_from_context,regulatory_details_required

def test_nullable_migration_idempotent_preserves_existing_rows():
 engine=create_engine('sqlite:///:memory:')
 with engine.begin() as c:
  c.execute(text('CREATE TABLE di_decisions(id VARCHAR(48) PRIMARY KEY, tenant_id VARCHAR(64), version INTEGER, title VARCHAR(180))'))
  c.execute(text("INSERT INTO di_decisions VALUES ('old','tenant-A',7,'Legacy decision')"))
  c.execute(text('CREATE TABLE r5_ai_risk_assessments(id VARCHAR(48) PRIMARY KEY, tenant_id VARCHAR(64))'))
  c.execute(text("INSERT INTO r5_ai_risk_assessments VALUES ('risk1','tenant-A')"))
 assert migrate(engine)['status']=='ok'
 assert migrate(engine)['status']=='ok'
 with engine.connect() as c:
  row=c.execute(text("SELECT tenant_id,version,confidence_basis,risk_tier,review_started_at FROM di_decisions WHERE id='old' ")).one()
  assert tuple(row)==('tenant-A',7,'unknown','unassessed',None)
  assert c.execute(text("SELECT count(*) FROM r5_ai_risk_assessments")).scalar()==1
 assert 'request_id' in {i['name'] for i in inspect(engine).get_columns('r5_ai_risk_assessments')}

def test_form_validation_and_context():
 init={'name':'Claims Triage Copilot','owner':'Risk Director','description':'Handles prioritization in claims operations with human review.'}
 autofill=autofill_from_context(init,None)
 assert autofill['title']==init['name']
 assert autofill['intended_use']==init['description']
 data={**autofill,'geography':'EU','assessment_source':'risk-doc-001','decision_id':'dec'}
 assert not errors_for_assessment(data)
 assert errors_for_assessment({**data,'intended_use':'Short'})['intended_use']
 assert regulatory_details_required('India','decision_support','unknown','Claims review')
 assert regulatory_details_required('Germany','assistive','unknown','Claims review')

def test_risk_submission_idempotent_and_new_decision_defaults():
 os.environ['DECISION_OS_IDENTITIES']=json.dumps({'a':{'user':'lead-A','tenant':'tenant-A','role':'lead'},'b':{'user':'lead-B','tenant':'tenant-B','role':'lead'}})
 configure('sqlite:///:memory:')
 c=TestClient(app)
 def req(method,path,token='a',**kw):return c.request(method,path,headers={'Authorization':'Bearer '+token},**kw)
 init=req('POST','/v1/initiatives',json={'name':'Claims Triage Copilot','owner':'Risk Director','description':'Pilot for processing claims'}).json()['id']
 decision=req('POST','/v1/intelligence/decisions',json={'initiative_id':init,'title':'Expand AI Knowledge to finance function','option_chosen':'Fund pilot','rationale':'Test claims productivity and validate the expected return','assumptions':[],'alternatives':[],'evidence_refs':[]})
 assert decision.status_code==201,decision.text
 d=decision.json(); assert d['tenant_id'] if 'tenant_id' in d else True
 assert d['version']==1 and d['risk_tier']=='unassessed' and d['confidence_basis']=='unknown'
 assert d['approved_at'] is None and d['review_started_at'] is None
 payload={'initiative_id':init,'decision_id':d['id'],'request_id':'repeat_token_01234567890123','title':'Claims R5 Assessment','ai_role':'deployer','geography':'India','intended_use':'Assist claims reviewers without automated decisions','classification':'review_required','owner':'Risk Director','assessment_source':'risk-doc-001','risk_factors':{}}
 first=req('POST','/v1/trust/assessments',json=payload);second=req('POST','/v1/trust/assessments',json=payload)
 assert first.status_code==201,first.text
 assert second.status_code==201,second.text
 assert first.json()['id']==second.json()['id']
 assert len(req('GET','/v1/trust/assessments').json())==1
 assert len(req('GET','/v1/trust/assessments',token='b').json())==0
 conflict=req('POST','/v1/trust/assessments',json={**payload,'decision_id':'different'})
 assert conflict.status_code in (404,422,409)
