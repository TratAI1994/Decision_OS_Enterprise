"""Decision OS domain: framework-independent contracts, gates and exact decision service."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

STAGES = {
    'discover': (),
    'value': ('discover',),
    'data': ('value',),
    'architecture': ('value',),
    'build': ('data','architecture'),
    'evaluation': ('build',),
    'security': ('evaluation',),
    'pilot': ('security',),
    'release': ('pilot',),
    'operate': ('release',),
}
REQUIRED = {
    'discover': ('problem','sponsor','baseline'), 'value': ('business_case','kpis'),
    'data': ('inventory','access_review','data_quality'),
    'architecture': ('hld','lld','threat_model'),
    'build': ('commit','ci_result','integration_tests'),
    'evaluation': ('dataset_version','evaluation_result','failure_cases'),
    'security': ('security_review','privacy_review'),
    'pilot': ('pilot_metrics','user_feedback'),
    'release': ('rollback_plan','service_owner','change_record'),
    'operate': ('slo','runbook','benefits_ledger'),
}

def fingerprint(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(',',':'), default=str, allow_nan=False).encode()).hexdigest()

def descendants(stage: str) -> set[str]:
    out = set()
    while True:
        new = {k for k, v in STAGES.items() if set(v).intersection(out | {stage})} - out - {stage}
        if not new: return out
        out |= new

def states(artifacts: list[dict], approvals: list[dict] | None = None) -> dict:
    by = {(a['stage'],a['key']): a for a in artifacts}
    signed = {a['stage']:a for a in (approvals or [])}
    result = {}
    for stage, deps in STAGES.items():
        missing = [key for key in REQUIRED[stage] if (stage,key) not in by or by[(stage,key)]['status'] != 'verified']
        blocked = [dep for dep in deps if result[dep]['status'] != 'complete']
        if blocked: status = 'blocked'
        elif missing: status = 'in_progress' if any(k[0]==stage for k in by) else 'ready'
        elif stage == 'release' and stage not in signed: status = 'awaiting_approval'
        else: status = 'complete'
        result[stage] = {'status':status,'depends_on':list(deps),'blocked_by':blocked,'missing':missing}
    return result

def optimize(spec: dict) -> dict:
    """True three-pass binary HiGHS solve with objective-preservation checks."""
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    items = spec['items']; n = len(items)
    if not 1 <= n <= 500: raise ValueError('Use 1 to 500 items')
    ids = [x['id'] for x in items]
    if len(set(ids)) != n: raise ValueError('Duplicate IDs')
    idx = {s:i for i,s in enumerate(ids)}
    cost = np.array([float(x['cost']) for x in items]); impact = np.array([float(x['impact']) for x in items]); secondary = np.array([float(x.get('secondary',0)) for x in items]); budget = float(spec['budget'])
    if not np.all(np.isfinite(np.r_[cost,impact,secondary,budget])) or np.any(cost < 0) or budget < 0: raise ValueError('Invalid finite nonnegative cost/budget values')
    vectors=[]; lo=[]; hi=[]
    def row(v,low=-np.inf,high=np.inf): vectors.append(v);lo.append(low);hi.append(high)
    row(cost,high=budget)
    for x in items:
        if x.get('requires'):
            if x['requires'] not in idx: raise ValueError('Unknown prerequisite')
            v=np.zeros(n);v[idx[x['id']]]=1;v[idx[x['requires']]]-=1;row(v,high=0)
    for a,b in spec.get('forbidden',[]):
        if a not in idx or b not in idx or a==b: raise ValueError('Invalid forbidden pair')
        v=np.zeros(n);v[idx[a]]=1;v[idx[b]]=1;row(v,high=1)
    for key in spec.get('required',[]):
        if key not in idx: raise ValueError('Unknown required item')
        v=np.zeros(n);v[idx[key]]=1;row(v,low=1,high=1)
    for key in spec.get('excluded',[]):
        if key not in idx: raise ValueError('Unknown excluded item')
        v=np.zeros(n);v[idx[key]]=1;row(v,low=0,high=0)
    row(np.ones(n),low=int(spec.get('min_items',0)),high=int(spec.get('max_items',n)))
    winners=[]
    for objective,preserve in ((-impact,impact),(-secondary,secondary),(cost,None)):
        result=milp(c=objective,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(np.array(vectors),np.array(lo),np.array(hi)),options={'time_limit':30,'mip_rel_gap':0})
        if result.status != 0 or result.x is None: return {'status':'not_proven_optimal','message':str(result.message),'selected':[]}
        winners=np.rint(result.x).astype(int)
        if preserve is not None:
            value=float(preserve @ winners); tolerance=max(1e-7,abs(value)*1e-9)
            row(preserve.copy(),low=value-tolerance)
    actual=float(cost @ winners)
    violations=[]
    for v,l,h in zip(vectors,lo,hi):
        val=float(np.asarray(v) @ winners)
        if val < l-1e-6 or val > h+1e-6: violations.append('constraint')
    return {'status':'optimal' if not violations else 'verification_failed','selected':[ids[i] for i in range(n) if winners[i]],'impact':float(impact@winners),'secondary':float(secondary@winners),'cost':actual,'budget':budget,'verified':not violations,'method':'scipy_highs_three_pass'}
