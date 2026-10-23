import json
import os
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.api import app, configure
from backend.db import engine_for
from backend.migration_r55 import run


def test_additive_migration_repeatable():
    configure('sqlite:///:memory:')
    e=engine_for('sqlite:///:memory:')
    from backend.db import Base
    from backend.intelligence import DecisionRecord
    Base.metadata.create_all(e,tables=[__import__('backend.db',fromlist=['Initiative']).Initiative.__table__, DecisionRecord.__table__])
    before=set(inspect(e).get_table_names())
    r=run(e,True)
    assert all(x.startswith('so_') for x in r['created'])
    again=run(e,True);assert again['created']==[]
    assert before.issubset(set(inspect(e).get_table_names()))

def test_end_to_end_strategy_tenant_stale_attribution_discovery():
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({'lead':{'user':'lead','tenant':'A','role':'lead'},'other':{'user':'other','tenant':'B','role':'lead'},'reviewer':{'user':'reviewer','tenant':'A','role':'reviewer'}})
    configure('sqlite:///:memory:');c=TestClient(app)
    def q(m,p,who='lead',**kw):return c.request(m,p,headers={'Authorization':'Bearer '+who},**kw)
    def post(p,j,who='lead'):
        x=q('POST','/v1/strategy/'+p,who,json=j);assert x.status_code==201,(p,x.text);return x.json()
    iid=q('POST','/v1/initiatives',json={'name':'Claims Copilot','owner':'Risk Lead'}).json()['id']
    d=q('POST','/v1/intelligence/decisions',json={'initiative_id':iid,'title':'Fund claims pilot','option_chosen':'Pilot','rationale':'Measure observed value first'}).json()['id']
    f=post('focus-areas',{'title':'Claims processing','owner':'CEO'})
    o=post('objectives',{'focus_id':f['id'],'title':'Reduce customer waiting','owner':'PMO','horizon':'2027-02-01'})
    k=post('key-results',{'objective_id':o['id'],'title':'Handling time reduction','unit':'percent','direction':'higher','baseline':0,'target':15,'target_date':'2027-02-01','measurement_owner':'Analyst','stale_after_days':7})
    assert q('GET','/v1/strategy/key-results').json()[0]['measurement']['state']=='NO_DATA'
    post('decision-links',{'key_result_id':k['id'],'decision_id':d})
    assert q('GET',f'/v1/strategy/lineage/{d}',who='other').status_code==404
    assert len(q('GET',f'/v1/strategy/lineage/{d}').json()['chains'])==1
    assert q('POST','/v1/strategy/decision-links',who='other',json={'key_result_id':k['id'],'decision_id':d}).status_code==404
    old=(datetime.now(UTC)-timedelta(days=10)).isoformat()
    post('observations',{'key_result_id':k['id'],'value':15,'observed_at':old,'source':'manual','source_ref':'survey-2026','confidence':'low','attribution':'correlated','limitations':'Changes to staffing'})
    assert q('GET','/v1/strategy/key-results').json()[0]['measurement']['state']=='STALE'
    current=datetime.now(UTC).isoformat()
    post('observations',{'key_result_id':k['id'],'value':8,'observed_at':current,'source':'manual','source_ref':'survey-new','confidence':'moderate','attribution':'correlated','limitations':'Seasonal confounding'})
    measurement=q('GET','/v1/strategy/key-results').json()[0]['measurement']
    assert measurement['state']=='IN_PROGRESS' and measurement['gap']==-7
    assert measurement['observation']['attribution']=='correlated'
    assert q('GET','/v1/strategy/key-results',who='other').json()==[]
    exp=post('experiments',{'decision_id':d,'customer_job':'Triage incoming claims faster','segment':'Claim agents','hypothesis':'Reduce handling time through AI triage','method':'pilot','metric':'hours saved','direction':'higher','threshold':15,'evidence_ref':'protocol-v1'})
    result=q('POST',f"/v1/strategy/experiments/{exp['id']}/result",json={'expected_version':1,'observed_value':8,'evidence_ref':'pilot-result'})
    assert result.status_code==200 and result.json()['result']=='not_supported'
    assert q('POST',f"/v1/strategy/experiments/{exp['id']}/result",json={'expected_version':1,'observed_value':100,'evidence_ref':'pilot-result'}).status_code==409
    a=post('assumptions',{'decision_id':d,'statement':'Claims workload follows current trend','confidence':'unknown'})
    assert q('POST',f"/v1/strategy/assumptions/{a['id']}/review",json={'expected_version':1,'validation_status':'supported','evidence_ref':'document-1'}).status_code==403
    assert q('POST',f"/v1/strategy/assumptions/{a['id']}/review",who='reviewer',json={'expected_version':1,'validation_status':'invalidated','evidence_ref':'document-1'}).status_code==200
