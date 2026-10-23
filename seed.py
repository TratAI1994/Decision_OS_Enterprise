"""Decision OS R5.5 demo seeder via existing authenticated FastAPI endpoints.

Dry-run by default; run with --apply and an issued lead/editor API token.
Creates clearly labeled synthetic demonstration records only, and never deletes records.
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta, datetime, timezone
import os
import sys
import requests

PREFIX='[DEMO R5.5]'
class Client:
    def __init__(self,base,token):
        self.base=base.rstrip('/');self.session=requests.Session()
        self.session.headers.update({'Authorization':f'Bearer {token}','Accept':'application/json'})
    def call(self,method,path,body=None):
        r=self.session.request(method,self.base+path,json=body,timeout=30)
        if not r.ok:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}: {r.text[:350]}')
        return r.json()
    def get(self,path):return self.call('GET',path)
    def post(self,path,body):return self.call('POST',path,body)

def ensure(client,endpoint,field,value,payload,apply,counts):
    matches=[x for x in client.get(endpoint) if x.get(field)==value]
    if len(matches)>1:raise RuntimeError(f'Duplicate existing {field}={value!r}; refusing ambiguous linkage')
    if matches:return matches[0]
    counts['planned']+=1
    print(f"{'CREATE' if apply else 'WOULD CREATE'} {endpoint}: {value}")
    if not apply:return None
    result=client.post(endpoint,payload);counts['created']+=1
    return result

def seed(client,apply=False):
    actor=client.get('/v1/me')
    if actor.get('role') not in ('admin','lead','editor'):
        raise RuntimeError('Seed requires an issued admin/lead/editor credential')
    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}; tenant: {actor.get('tenant', actor.get('tenant_id','unknown'))}; actor: {actor.get('user','unknown')}")
    counts={'planned':0,'created':0}
    focus_title=f'{PREFIX} Customer Operations Transformation'
    f=ensure(client,'/v1/strategy/focus-areas','title',focus_title,{'title':focus_title,'owner':'Demo Transformation Lead','description':'SYNTHETIC EXAMPLE: AI-assisted claims processing pilot. No real company data or verified economic benefits.'},apply,counts)
    if not f:
        print('DRY RUN: child records depend on newly created parent IDs. Run with --apply to populate them.');return counts
    objective=f'{PREFIX} Improve claims handling efficiency'
    obj=ensure(client,'/v1/strategy/objectives','title',objective,{'focus_id':f['id'],'title':objective,'owner':'Demo Product Owner','horizon':str(date.today()+timedelta(days=90))},apply,counts)
    if not obj:return counts
    krname=f'{PREFIX} Reduce median handling time by 15%'
    kr=ensure(client,'/v1/strategy/key-results','title',krname,{'objective_id':obj['id'],'title':krname,'unit':'% reduction','direction':'higher','baseline':0.0,'target':15.0,'target_date':str(date.today()+timedelta(days=90)),'measurement_owner':'Demo Analytics Lead','stale_after_days':7},apply,counts)
    if not kr:return counts
    # Link only existing decisions. Never create or approve an investment decision.
    existing=client.get('/v1/intelligence/decisions')
    relevant=[d for d in existing if 'claim' in d.get('title','').lower()]
    if not relevant:
        print('INFO No pre-existing Claims decision; strategy records created but funding and discovery remain unlinked.');return counts
    d=relevant[0];links=client.get('/v1/strategy/decision-links')
    if not any(x['decision_id']==d['id'] and x['key_result_id']==kr['id'] for x in links):
        counts['planned']+=1
        if apply:client.post('/v1/strategy/decision-links',{'decision_id':d['id'],'key_result_id':kr['id']});counts['created']+=1
    statement=f'{PREFIX} Training completion is sufficient to support the claims efficiency target'
    ensure(client,'/v1/strategy/assumptions','statement',statement,{'decision_id':d['id'],'statement':statement,'confidence':'unknown','evidence_ref':''},apply,counts)
    hypothesis=f'{PREFIX} A controlled pilot will show at least an 8% reduction in median handling time'
    ensure(client,'/v1/strategy/experiments','hypothesis',hypothesis,{'decision_id':d['id'],'customer_job':'Review and route incoming claims efficiently','segment':'Synthetic claims operations pilot','hypothesis':hypothesis,'method':'pilot','metric':'Median handling-time reduction (%)','direction':'higher','threshold':8.0,'evidence_ref':'DEMO-PROTOCOL-NOT-VERIFIED'},apply,counts)
    # No invented observation: any real metric must be imported or entered from actual evidence.
    print('INFO No outcome observation seeded: 8% is a hypothesis threshold, NOT an observed result.')
    return counts

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true',help='Write clearly labeled synthetic data (default dry-run)')
    p.add_argument('--api',default=os.getenv('DECISION_OS_API_URL','http://localhost:8001'))
    p.add_argument('--token',default=os.getenv('DECISION_OS_UI_TOKEN',''),help='Issued credential (prefer environment variable)')
    args=p.parse_args()
    if not args.token:sys.exit('Set DECISION_OS_UI_TOKEN to a valid issued lead/editor credential; no token is bundled.')
    try:
        counts=seed(Client(args.api,args.token),args.apply)
        print('Finished:',counts)
    except (requests.RequestException,RuntimeError) as e:sys.exit(f'Seed stopped safely: {e}')
if __name__=='__main__':main()
