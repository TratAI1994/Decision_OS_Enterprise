"""R9.8 immutable evidence envelope validation. Pure stdlib, fail closed.

This module authenticates neither remote APIs nor reviewers: a trusted collector
must supply its independently authenticated source identity.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from typing import Any

class ProvenanceError(ValueError):
    pass

@dataclass(frozen=True)
class SourceIdentity:
    source_system: str
    principal_id: str
    authenticated: bool
    method: str

REQUIRED = ('tenant_id','source_system','source_record','captured_at','content_sha256','schema_version')

def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def utc_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProvenanceError('captured_at must be an ISO8601 timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ProvenanceError('captured_at must include a timezone')
    return dt.astimezone(timezone.utc)

def prepare_evidence(envelope: dict[str,Any], content: bytes, actor_tenant: str, source: SourceIdentity, *, now: datetime|None=None) -> dict[str,Any]:
    """Only a trusted ingestion service may call this after real credential verification.

    Returns an independently checkable envelope; it does NOT mark evidence verified.
    """
    if not isinstance(envelope,dict): raise ProvenanceError('evidence envelope must be object')
    if any(not envelope.get(k) for k in REQUIRED): raise ProvenanceError('missing required evidence fields')
    if set(envelope)-set(REQUIRED)-{'metadata'}: raise ProvenanceError('unexpected evidence fields')
    if not isinstance(content,bytes) or not content: raise ProvenanceError('nonempty evidence bytes required')
    if len(content)>16*1024*1024: raise ProvenanceError('evidence exceeds 16 MiB maximum')
    if envelope['schema_version'] != '1.0': raise ProvenanceError('unsupported evidence version')
    if not hmac.compare_digest(str(envelope['tenant_id']),str(actor_tenant)): raise ProvenanceError('tenant mismatch')
    if not source.authenticated or source.method not in {'mtls','oidc','signed_webhook','workload_identity'}:
        raise ProvenanceError('independently authenticated collector required')
    if source.source_system != envelope['source_system'] or not source.principal_id:
        raise ProvenanceError('source principal mismatch')
    date=utc_time(envelope['captured_at'])
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if date>current: raise ProvenanceError('future captured_at')
    supplied=str(envelope['content_sha256'])
    digest=sha256(content).hexdigest()
    if len(supplied)!=64 or not hmac.compare_digest(supplied,digest): raise ProvenanceError('content digest mismatch')
    out={k:envelope[k] for k in REQUIRED}
    out['captured_at']=date.isoformat()
    out['collector_principal']=source.principal_id
    out['collector_authentication']=source.method
    out['verification_status']='COLLECTOR_AUTHENTICATED_CONTENT_MATCHED'
    out['limitations']='Authenticity of data origin and content match do not establish measurement accuracy or causal attribution.'
    out['envelope_sha256']=sha256(canonical_bytes(out)).hexdigest()
    return out

def verify_envelope(snapshot:dict[str,Any]) -> bool:
    value=dict(snapshot)
    stored=value.pop('envelope_sha256',None)
    return isinstance(stored,str) and hmac.compare_digest(stored,sha256(canonical_bytes(value)).hexdigest())
