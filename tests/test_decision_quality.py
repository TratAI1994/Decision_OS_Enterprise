import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
spec=importlib.util.spec_from_file_location('dq',Path(__file__).resolve().parents[1]/'ui'/'decision_quality.py')
m=importlib.util.module_from_spec(spec)
import sys, types
sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_quality_unknown():
    r=m.quality_score({},False)
    assert r.score is None and len(r.missing)==7 and r.governance_warning

def test_quality_hypothetical():
    r=m.quality_score({k:80 for k in m.WEIGHTS},True)
    assert r.score==80 and not r.governance_warning

def test_stale_precedes_difference():
    t=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
    r=m.assessment_state(20,20,observed_at=t,stale_after_days=7,evidence_ref='ref')
    assert r['state']=='STALE'

def test_difference_cannot_invalidate():
    r=m.assessment_state(20,5,observed_at=datetime.now(timezone.utc).isoformat(),stale_after_days=7,evidence_ref='ref')
    assert r['state']=='OBSERVED — HUMAN REVIEW REQUIRED' and r['reviewed_status']=='unknown'

def test_missing_evidence_no_observation():
    r=m.assessment_state(20,5,observed_at=datetime.now(timezone.utc).isoformat(),stale_after_days=7)
    assert r['state']=='NOT MEASURED'

def test_api_tenant_boundary():
    calls=[]
    def api(method,path,quiet=False):
        calls.append((method,path))
        if path.endswith('/decisions'):return [{'id':'authorized','title':'ok'}]
        return [{'id':'x','decision_id':'other','statement':'private'}]
    assert m.fetch_context(api,'unauthorized')['error']
    assert len(calls)==1
    result=m.fetch_context(api,'authorized')
    assert result['assumptions']==[]
    assert all(x[0]=='GET' for x in calls)
