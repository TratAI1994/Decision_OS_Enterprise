#!/usr/bin/env python3
"""Idempotent, demo-only seed via authenticated REST. Never writes directly to PostgreSQL.

Windows: python seed_demo.py --base http://127.0.0.1:8001
Reads bootstrap lead/finance credentials from local .env, never prints them.
Requires existing running API and DECISION_OS_IDENTITIES in .env.
"""
from __future__ import annotations
import argparse, json, os, urllib.request, urllib.error
from pathlib import Path

PREFIX='[DEMO • SYNTHETIC] '
SCENARIOS=[
 {'name':'Claims Triage Copilot','owner':'Demo: Claims Operations Director','description':'DEMO DATA / FICTIONAL. Reduce manual claims triage, review accuracy and turnaround time; target: 15% faster processing. All figures synthetic, not financial evidence.','months':[('2026-07',125000,99000,11000),('2026-08',125000,108000,11800),('2026-09',125000,112000,12100)]},
 {'name':'Engineering Knowledge Assistant','owner':'Demo: VP Engineering','description':'DEMO DATA / FICTIONAL. Retrieval assistant for internal engineering documentation; track time-to-answer and active-user adoption. Benefits are fictional self-reports.','months':[('2026-07',78000,45000,8400),('2026-08',78000,56000,9200),('2026-09',78000,67000,9700)]},
 {'name':'Multi-Echelon Inventory Optimization','owner':'Demo: Supply Chain Director','description':'DEMO DATA / FICTIONAL. Improve inventory allocation using constrained optimization; measure fulfillment cost and stockouts. Figures are synthetic.','months':[('2026-08',155000,96000,18500),('2026-09',155000,124000,19500)]},
]

def local_env(path:Path)->dict:
    if not path.exists():raise RuntimeError(f'Missing {path}. Run setup_local.py first.')
    values={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            a,b=line.split('=',1);values[a.strip()]=b.strip()
    return values

def choose_token(env):
    reg=json.loads(env.get('DECISION_OS_IDENTITIES','{}'))
    for role in ('lead','admin'):
        for token,identity in reg.items():
            if identity.get('role')==role and identity.get('tenant')=='local-demo':return token
    raise RuntimeError('A lead/admin local-demo credential is required in .env')

def request(base,token,method,path,payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(base+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {path}: HTTP {e.code} {e.read(400).decode(errors="replace")}') from e

def seed(base,token):
    identities=request(base,token,'GET','/v1/me')
    if identities.get('tenant')!='local-demo':raise RuntimeError('Refusing to seed a non-demo tenant')
    existing=request(base,token,'GET','/v1/initiatives')
    names={x['name']:x['id'] for x in existing}
    made=0;skip=0
    for demo in SCENARIOS:
        name=PREFIX+demo['name']
        if name not in names:
            obj=request(base,token,'POST','/v1/initiatives',{'name':name,'owner':demo['owner'],'description':demo['description']})
            names[name]=obj['id'];made+=1;print('Created initiative:',name)
        else:skip+=1;print('Existing initiative:',name)
        # Benefits are guarded by the API's unique initiative_id/period constraint.
        # Existing periods return 409; that is an expected idempotent no-op.
        for month,planned,reported,run_cost in demo['months']:
            try:
                request(base,token,'POST',f'/v1/initiatives/{names[name]}/benefits',{'period':month,'planned':planned,'reported':reported,'run_cost':run_cost,'evidence_reference':f'SYNTHETIC-DEMO-ONLY/{demo["name"].replace(" ","_")}/{month}'})
                print('  Added fictional self-reported benefit',month)
            except RuntimeError as ex:
                if 'HTTP 409' not in str(ex):raise
                print('  Skipped existing period',month)
    print(f'Complete: {made} initiatives created, {skip} already existed; sample data is FICTIONAL and self-reported.')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',default='http://127.0.0.1:8001')
    ap.add_argument('--env',default=str(Path(__file__).resolve().parent/'.env'))
    args=ap.parse_args()
    env=local_env(Path(args.env));seed(args.base.rstrip('/'),choose_token(env))
