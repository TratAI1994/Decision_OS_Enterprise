"""R9.9 live negative-control validation. No production writes without explicit acknowledgement.

This tool generates synthetic evidence ONLY and never asks for collector secrets on the CLI.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

ENDPOINT = '/v1/source-evidence/ingest'

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

@dataclass(frozen=True)
class Result:
    name: str
    result: str
    detail: str


def signed_request(payload:bytes, *, tenant:str, source:str, key_id:str, key_hex:str,
                   source_record:str, timestamp:str|None=None, nonce:str|None=None) -> tuple[bytes,dict[str,str]]:
    if not payload or len(payload)>1024*1024:
        raise ValueError('Payload must be 1 byte to 1 MiB')
    if len(bytes.fromhex(key_hex)) < 32:
        raise ValueError('Collector key must contain at least 32 bytes')
    timestamp=timestamp or datetime.now(timezone.utc).isoformat()
    nonce=nonce or secrets.token_urlsafe(24)
    digest=hashlib.sha256(payload).hexdigest()
    msg=canonical({'timestamp':timestamp, 'nonce':nonce,'tenant':tenant,'source':source,
                   'source_record':source_record,'sha256':digest})
    signature=hmac.new(bytes.fromhex(key_hex),msg,hashlib.sha256).hexdigest()
    return payload, {'X-Tenant':tenant,'X-Source':source,'X-Source-Record':source_record,
        'X-Key-Id':key_id,'X-Timestamp':timestamp,'X-Nonce':nonce,
        'X-Content-SHA256':digest,'X-Signature':signature,'Content-Type':'application/octet-stream'}


def send(url:str, payload:bytes,headers:dict[str,str], timeout:int=15)->tuple[int,dict]:
    req=urllib.request.Request(url.rstrip('/')+ENDPOINT,data=payload,headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            raw=response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        # Deliberately do not log auth headers or sensitive body contents.
        error.read()
        return error.code, {}


def perform(api:str,tenant:str,source:str,key_id:str,key_hex:str,
            transport:Callable=send, concurrent:bool=True)->tuple[list[Result],dict]:
    report={}
    results=[]
    source_record='r99-live-'+secrets.token_hex(7)
    original=canonical({'assurance_suite':'r99-negative-controls','synthetic':True,
                        'marker':secrets.token_hex(8),'pass':True})
    payload,headers=signed_request(original,tenant=tenant,source=source,key_id=key_id,
                                   key_hex=key_hex,source_record=source_record)
    status,data=transport(api,payload,headers)
    evidence_id=data.get('id') if isinstance(data,dict) else None
    good=status==201 and data.get('trust_state')=='AUTHENTICATED_COLLECTOR_CONTENT_MATCHED' and data.get('business_validated') is False and data.get('content_sha256')==hashlib.sha256(original).hexdigest()
    results.append(Result('signed_ingestion','PASS' if good else 'FAIL',f'HTTP {status}; expected 201 with matching digest and limited trust classification'))
    report['evidence_id']=evidence_id if good else None
    if not good:
        results.extend([Result(n,'NOT_TESTED','Requires successful signed baseline ingestion') for n in ('nonce_replay','modified_bytes','modified_digest','concurrent_same_nonce')])
        return results,report
    replay_status,_=transport(api,payload,headers)
    results.append(Result('nonce_replay','PASS' if replay_status==409 else 'FAIL',f'HTTP {replay_status}; expected 409'))
    changed=bytearray(payload);changed[-1]^=1
    changed_status,_=transport(api,bytes(changed),headers)
    results.append(Result('modified_bytes','PASS' if changed_status in (401,422) else 'FAIL',f'HTTP {changed_status}; expected 401 or 422'))
    changed_headers=dict(headers);changed_headers['X-Content-SHA256']='0'*64
    digest_status,_=transport(api,payload,changed_headers)
    results.append(Result('modified_digest','PASS' if digest_status==401 else 'FAIL',f'HTTP {digest_status}; expected 401'))
    if concurrent:
        race_payload,race_headers=signed_request(canonical({'race':secrets.token_hex(8),'synthetic':True}),tenant=tenant,source=source,key_id=key_id,key_hex=key_hex,source_record=source_record+'-race')
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(transport,api,race_payload,race_headers) for _ in range(2)]
            codes=sorted(f.result()[0] for f in futures)
        results.append(Result('concurrent_same_nonce','PASS' if codes==[201,409] else 'FAIL',f'HTTP statuses {codes}; expected [201,409]'))
    else:results.append(Result('concurrent_same_nonce','NOT_TESTED','Concurrency disabled'))
    return results,report


def validate_db_guard(dbname:str, acknowledgment:str):
    if acknowledgment!='I_UNDERSTAND_TEST_DATABASE_ONLY':
        raise ValueError('Explicit disposable database acknowledgement required')
    if not (dbname.endswith('_test') or dbname.endswith('_ci') or dbname.startswith('test_')):
        raise ValueError('Database name must identify a disposable *_test, *_ci or test_* database')


def database_proof(url:str, acknowledgment:str)->list[Result]:
    """Synthetic fixture and mutation attempts in a disposable PostgreSQL database."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    dbname=make_url(url).database or ''
    validate_db_guard(dbname,acknowledgment)
    engine=create_engine(url,connect_args={'connect_timeout':5})
    if engine.dialect.name!='postgresql':raise ValueError('PostgreSQL required')
    results=[]
    fixture='r99-proof-'+secrets.token_hex(12)
    try:
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO di_authenticated_evidence (id,tenant_id,source_system,source_record,key_id,nonce,collected_at,payload_bytes,payload_sha256,envelope_json,envelope_sha256) VALUES (:id,:tenant,:source,:record,:kid,:nonce,now(),:payload,:hash,:envelope,:ehash)'),
                 {'id':fixture,'tenant':'r99-assurance-test','source':'synthetic',
                  'record':fixture,'kid':'test-key','nonce':fixture,
                  'payload':b'test-fixture','hash':hashlib.sha256(b'test-fixture').hexdigest(),
                  'envelope':'{}','ehash':'0'*64})
        for operation,sql in [
            ('postgres_update_trigger','UPDATE di_authenticated_evidence SET payload_sha256=:bad WHERE id=:id'),
            ('postgres_delete_trigger','DELETE FROM di_authenticated_evidence WHERE id=:id')]:
            with engine.connect() as conn:
                tx=conn.begin()
                try:
                    conn.execute(text(sql),{'id':fixture,'bad':'0'*64})
                except Exception:
                    results.append(Result(operation,'PASS','Database rejected mutation'))
                else:
                    results.append(Result(operation,'FAIL','Database permitted mutation; transaction rolled back'))
                finally:tx.rollback()
        with engine.connect() as conn:
            row=conn.execute(text('SELECT payload_sha256 FROM di_authenticated_evidence WHERE id=:id'),{'id':fixture}).scalar_one_or_none()
        intact=row==hashlib.sha256(b'test-fixture').hexdigest()
        results.append(Result('postgres_row_preserved','PASS' if intact else 'FAIL','Synthetic row remains unchanged'))
    finally:engine.dispose()
    return results

def main(argv=None):
    parser=argparse.ArgumentParser(description='R9.9 source-authentication negative-control live checks')
    parser.add_argument('--api',default=os.getenv('DECISION_OS_EVIDENCE_API','http://127.0.0.1:8001'))
    parser.add_argument('--output',default='r99_assurance_report.json')
    parser.add_argument('--no-concurrency',action='store_true')
    parser.add_argument('--postgres-url',default=os.getenv('R99_DISPOSABLE_POSTGRES_URL'))
    args=parser.parse_args(argv)
    if not args.api.startswith(('http://127.0.0.1:', 'http://localhost:', 'https://')):
        parser.error('Require localhost HTTP or HTTPS; refuse remote plaintext collector secrets')
    env=os.environ
    for name in ('DECISION_OS_TENANT','DECISION_OS_COLLECTOR_KEY_ID','DECISION_OS_COLLECTOR_KEY_HEX'):
        if not env.get(name):parser.error(f'Missing environment variable {name}')
    result,meta=perform(args.api,env['DECISION_OS_TENANT'],env.get('DECISION_OS_SOURCE','jenkins'),env['DECISION_OS_COLLECTOR_KEY_ID'],env['DECISION_OS_COLLECTOR_KEY_HEX'],concurrent=not args.no_concurrency)
    # Distinguish API success from database proof; never connect to production automatically.
    if args.postgres_url:
        try:
            result += database_proof(args.postgres_url,env.get('R99_TEST_DB_ACK',''))
        except Exception as exc:
            result.append(Result('postgres_trigger','NOT_TESTED',f'Disposable database proof not executed: {type(exc).__name__}'))
    else:
        result.append(Result('postgres_trigger','NOT_TESTED','Requires explicit disposable PostgreSQL connection and test acknowledgement'))
    result.append(Result('cross_tenant_retrieval','NOT_TESTED','Requires a distinct authorized tenant token; do not infer from HMAC scope'))
    result.append(Result('external_anchoring','NOT_IMPLEMENTED','No external cryptographic anchor configured'))
    summary={'schema':'r99.9-live-assurance-v1','generated_at':datetime.now(timezone.utc).isoformat(),
             'endpoint':args.api.rstrip('/')+ENDPOINT,'evidence_id':meta.get('evidence_id'),
             'results':[asdict(x) for x in result]}
    summary['certified']=False
    Path(args.output).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    for item in result:print(f'{item.result:15} {item.name}: {item.detail}')
    print('Report:',args.output)
    return 1 if any(x.result=='FAIL' for x in result) else 0

if __name__=='__main__':sys.exit(main())
