"""R9.9 authenticated raw-byte evidence intake. Fail-closed HMAC boundary.

Separate transport authentication, provenance validation, and persistence.
Uses deployment-provisioned collector keys; never accepts verification flags from clients.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Callable
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import Column, DateTime, LargeBinary, String, UniqueConstraint, select
from sqlalchemy.orm import Session
from .db import Base
from .provenance_contract import SourceIdentity, prepare_evidence, verify_envelope, ProvenanceError, canonical_bytes

MAX_BYTES = 1024 * 1024
MAX_CLOCK_SKEW_SECONDS = 300
ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$')

class AuthenticatedEvidence(Base):
    __tablename__ = 'di_authenticated_evidence'
    id = Column(String(48), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    source_system = Column(String(128), nullable=False)
    source_record = Column(String(128), nullable=False)
    key_id = Column(String(128), nullable=False)
    nonce = Column(String(128), nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    payload_bytes = Column(LargeBinary, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    envelope_json = Column(String, nullable=False)
    envelope_sha256 = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id','source_system','key_id','nonce', name='uq_di_r99_nonce'),)

class KeyRegistry:
    """Key IDs are explicitly tenant/source scoped; accepts only 32+ byte random keys."""
    def __init__(self, records: dict):
        self.records = {}
        for tenant, sources in records.items():
            for source, keys in sources.items():
                for key_id, value in keys.items():
                    key = bytes.fromhex(value)
                    if len(key) < 32: raise ValueError('HMAC collector keys must be >= 32 bytes')
                    self.records[(tenant,source,key_id)] = key

    @classmethod
    def from_environment(cls):
        return cls(json.loads(os.getenv('DECISION_OS_COLLECTOR_KEYS_JSON','{}')))

    def key(self, tenant: str, source: str, kid: str) -> bytes | None:
        return self.records.get((tenant,source,kid))

def signature_message(timestamp: str, nonce: str, tenant: str, source: str,
                      source_record: str, digest: str) -> bytes:
    return canonical_bytes({'timestamp':timestamp,'nonce':nonce,'tenant':tenant,
                            'source':source,'source_record':source_record,'sha256':digest})

def verify_collector(*, registry:KeyRegistry, tenant:str, source:str, key_id:str,
                     source_record:str, timestamp:str, nonce:str, digest:str, signature:str,
                     now:datetime|None=None) -> None:
    for value in (tenant,source,key_id,source_record,nonce):
        if not ID_PATTERN.fullmatch(value): raise ValueError('Invalid collector identifier')
    if not re.fullmatch(r'[0-9a-f]{64}', digest) or not re.fullmatch(r'[0-9a-f]{64}',signature):
        raise ValueError('Malformed digest or signature')
    try:
        instant = datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        if instant.tzinfo is None: raise ValueError('Timezone missing')
        instant = instant.astimezone(timezone.utc)
    except (TypeError,ValueError) as exc:
        raise ValueError('Invalid signed timestamp') from exc
    present = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if abs((present-instant).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
        raise ValueError('Expired or future signature timestamp')
    key = registry.key(tenant,source,key_id)
    if key is None: raise PermissionError('Unknown collector key')
    expected = hmac.new(key,signature_message(timestamp,nonce,tenant,source,source_record,digest),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature): raise PermissionError('Signature mismatch')

def check_stored(item:AuthenticatedEvidence) -> bool:
    raw=bytes(item.payload_bytes)
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),item.payload_sha256): return False
    try: env=json.loads(item.envelope_json)
    except (TypeError,ValueError): return False
    if not verify_envelope(env): return False
    if env.get('tenant_id') != item.tenant_id or env.get('source_system') != item.source_system:
        return False
    return hmac.compare_digest(env.get('content_sha256',''),item.payload_sha256) and hmac.compare_digest(env.get('envelope_sha256',''),item.envelope_sha256)

def build_router(identity:Callable, session:Callable, require:Callable, registry:KeyRegistry|None=None):
    router=APIRouter(prefix='/v1/source-evidence',tags=['R9.9 Authenticated Evidence'])
    keys=registry or KeyRegistry.from_environment()

    @router.post('/ingest', status_code=201)
    async def ingest(request:Request, db:Session=Depends(session),
                     x_tenant:str=Header(...),x_source:str=Header(...),
                     x_key_id:str=Header(...),x_source_record:str=Header(...),
                     x_timestamp:str=Header(...),x_nonce:str=Header(...),
                     x_content_sha256:str=Header(...),x_signature:str=Header(...)):
        # Bound payload BEFORE reading into memory; reject missing/oversized content-length.
        length=request.headers.get('content-length')
        if length is None or not length.isdecimal() or not 0<int(length)<=MAX_BYTES:
            raise HTTPException(413,'Evidence content length required (1 MiB maximum)')
        try:
            verify_collector(registry=keys,tenant=x_tenant,source=x_source,key_id=x_key_id,
                             source_record=x_source_record,timestamp=x_timestamp,nonce=x_nonce,
                             digest=x_content_sha256,signature=x_signature)
        except PermissionError as exc: raise HTTPException(401,str(exc)) from exc
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        parts=[]
        received=0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_BYTES or received > int(length):
                raise HTTPException(413,'Invalid payload size')
            parts.append(chunk)
        content=b''.join(parts)
        if received!=int(length): raise HTTPException(413,'Invalid payload size')
        if not hmac.compare_digest(hashlib.sha256(content).hexdigest(),x_content_sha256):
            raise HTTPException(422,'Content hash mismatch')
        captured=datetime.fromisoformat(x_timestamp.replace('Z','+00:00')).astimezone(timezone.utc)
        envelope={'tenant_id':x_tenant,'source_system':x_source,'source_record':x_source_record,
                  'captured_at':captured.isoformat(),'content_sha256':x_content_sha256,'schema_version':'1.0'}
        try:
            prepared=prepare_evidence(envelope,content,x_tenant,SourceIdentity(x_source,x_key_id,True,'signed_webhook'))
        except ProvenanceError as exc: raise HTTPException(422,str(exc)) from exc
        item=AuthenticatedEvidence(id=secrets.token_hex(16),tenant_id=x_tenant,source_system=x_source,
            source_record=x_source_record,key_id=x_key_id,nonce=x_nonce,collected_at=datetime.now(timezone.utc),
            payload_bytes=content,payload_sha256=x_content_sha256,envelope_json=canonical_bytes(prepared).decode(),
            envelope_sha256=prepared['envelope_sha256'])
        db.add(item)
        try: db.commit()
        except Exception as exc:
            db.rollback()
            # Nonce replay always rejects, including exact retransmissions; caller gets no alternate identity.
            raise HTTPException(409,'Replay nonce or append conflict') from exc
        return {'id':item.id,'tenant_id':x_tenant,'source_system':x_source,
                'content_sha256':x_content_sha256,'trust_state':'AUTHENTICATED_COLLECTOR_CONTENT_MATCHED',
                'business_validated':False,'external_anchor_verified':False}

    @router.get('/{evidence_id}')
    def read(evidence_id:str,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','reviewer','risk','auditor','finance'})
        item=db.scalar(select(AuthenticatedEvidence).where(AuthenticatedEvidence.id==evidence_id,
                                                          AuthenticatedEvidence.tenant_id==actor.tenant))
        if item is None: raise HTTPException(404,'Evidence not found')
        valid=check_stored(item)
        return {'id':item.id,'integrity_valid':valid,'tenant_id':item.tenant_id,'source_system':item.source_system,
                'source_record':item.source_record,'content_sha256':item.payload_sha256,
                'envelope_sha256':item.envelope_sha256,'trust_state':'TAMPER_DETECTED' if not valid else 'AUTHENTICATED_COLLECTOR_CONTENT_MATCHED',
                'business_validated':False,'external_anchor_verified':False}
    return router
