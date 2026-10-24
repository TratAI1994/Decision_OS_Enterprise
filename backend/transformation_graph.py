"""R10b+ cross-domain lineage projection. Not a source of business truth.

Standard library only. Source events are supplied by trusted backend adapters; this
module deliberately has no public mutation endpoint and no SQL string interpolation.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json, re, sqlite3
from typing import Any

KINDS = frozenset('OBJECTIVE INITIATIVE RISK ARCHITECTURE DECISION EVIDENCE PIPELINE_RUN DEPLOYMENT OUTCOME FINANCE_RECONCILIATION'.split())
RELATIONS = frozenset('ADVANCES HAS_RISK MITIGATES IMPLEMENTS JUSTIFIES SUPPORTED_BY PRODUCED DEPLOYED_AS MEASURED_BY RECONCILED_BY SUPERSEDES'.split())
ALLOWED = {
 'ADVANCES':{('INITIATIVE','OBJECTIVE')},
 'HAS_RISK':{('INITIATIVE','RISK'),('ARCHITECTURE','RISK')},
 'MITIGATES':{('DECISION','RISK')},
 'IMPLEMENTS':{('ARCHITECTURE','INITIATIVE'),('DECISION','ARCHITECTURE')},
 'JUSTIFIES':{('DECISION','INITIATIVE')},
 'SUPPORTED_BY':{('DECISION','EVIDENCE'),('RISK','EVIDENCE'),('OUTCOME','EVIDENCE'),('DEPLOYMENT','EVIDENCE')},
 'PRODUCED':{('PIPELINE_RUN','EVIDENCE')},
 'DEPLOYED_AS':{('PIPELINE_RUN','DEPLOYMENT')},
 'MEASURED_BY':{('DEPLOYMENT','OUTCOME'),('INITIATIVE','OUTCOME')},
 'RECONCILED_BY':{('OUTCOME','FINANCE_RECONCILIATION')},
 'SUPERSEDES':{(k,k) for k in KINDS}
}

class GraphError(ValueError): pass
class GapError(GraphError): pass

def canonical(v:Any)->str: return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(v:Any)->str:return hashlib.sha256(canonical(v).encode()).hexdigest()
def require_id(v:str)->str:
 if not isinstance(v,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}',v):raise GraphError('invalid identifier')
 return v

def utc(value:str)->str:
 try:
  t=datetime.fromisoformat(value.replace('Z','+00:00'))
  if t.utcoffset() is None:raise ValueError('naive timestamp')
  return t.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except (ValueError,TypeError,AttributeError) as exc:raise GraphError('timestamp must be timezone-aware ISO8601') from exc

@dataclass(frozen=True)
class SourceEvent:
 tenant:str; stream:str; sequence:int; event_id:str; occurred_at:str; nodes:tuple[dict,...]; edges:tuple[dict,...]; source_digest:str

 def __post_init__(self):
  require_id(self.tenant); require_id(self.stream); require_id(self.event_id)
  if type(self.sequence) is not int or self.sequence<1: raise GraphError('invalid sequence')
  utc(self.occurred_at)
  if not re.fullmatch(r'[0-9a-f]{64}',self.source_digest):raise GraphError('source_digest must be SHA256 hex')

class GraphProjection:
 def __init__(self,connection:sqlite3.Connection):
  self.db=connection
  self.db.execute('PRAGMA foreign_keys=ON')
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS tkg_events(tenant TEXT NOT NULL,stream TEXT NOT NULL,seq INTEGER NOT NULL,event_id TEXT NOT NULL,hash TEXT NOT NULL,PRIMARY KEY(tenant,stream,seq),UNIQUE(tenant,event_id));
  CREATE TABLE IF NOT EXISTS tkg_nodes(tenant TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,source_ref TEXT NOT NULL,source_version TEXT NOT NULL,trust_state TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(tenant,id));
  CREATE TABLE IF NOT EXISTS tkg_edges(tenant TEXT NOT NULL,id TEXT NOT NULL,src TEXT NOT NULL,dst TEXT NOT NULL,relation TEXT NOT NULL,source_event TEXT NOT NULL,PRIMARY KEY(tenant,id),FOREIGN KEY(tenant,src) REFERENCES tkg_nodes(tenant,id),FOREIGN KEY(tenant,dst) REFERENCES tkg_nodes(tenant,id));
  CREATE INDEX IF NOT EXISTS tkg_outgoing ON tkg_edges(tenant,src);
  ''')

 def apply(self,e:SourceEvent)->bool:
  """Atomic, ordered idempotent projection of authenticated source event references.
  Caller MUST validate collector and signature before constructing SourceEvent.
  """
  nodes=list(e.nodes); edges=list(e.edges)
  for n in nodes:
   require_id(n['id']);require_id(n['source_ref'])
   if n['kind'] not in KINDS: raise GraphError('invalid node kind')
   if n['trust_state'] not in ('CLAIM','OBSERVED','PROVENANCE_CAPTURED','AUTHENTICATED_COLLECTOR_CONTENT_MATCHED','SOURCE_VERIFIED','EXTERNALLY_ANCHORED','AUDIT_DEFENSIBLE'):raise GraphError('invalid trust state')
   if not str(n['source_version']):raise GraphError('missing source version')
  for x in edges:
   require_id(x['id']);require_id(x['src']);require_id(x['dst'])
   if x['relation'] not in RELATIONS:raise GraphError('invalid relation')
  record={'tenant':e.tenant,'stream':e.stream,'sequence':e.sequence,'event_id':e.event_id,'occurred_at':utc(e.occurred_at),'source_digest':e.source_digest,'nodes':nodes,'edges':edges}
  h=digest(record)
  with self.db:
   existing=self.db.execute('SELECT hash FROM tkg_events WHERE tenant=? AND stream=? AND seq=?',(e.tenant,e.stream,e.sequence)).fetchone()
   if existing:
    if existing[0]!=h:raise GraphError('conflicting source event retry')
    return False
   seq=self.db.execute('SELECT COALESCE(MAX(seq),0) FROM tkg_events WHERE tenant=? AND stream=?',(e.tenant,e.stream)).fetchone()[0]
   if e.sequence!=seq+1:raise GapError('source stream out of order')
   for n in nodes:
    prior=self.db.execute('SELECT kind,source_ref,source_version,trust_state,payload FROM tkg_nodes WHERE tenant=? AND id=?',(e.tenant,n['id'])).fetchone()
    item=(n['kind'],n['source_ref'],str(n['source_version']),n['trust_state'],canonical(n.get('payload',{})))
    if prior and prior!=item:raise GraphError('node collision: versioned identifier required')
    self.db.execute('INSERT OR IGNORE INTO tkg_nodes VALUES(?,?,?,?,?,?,?)',(e.tenant,n['id'],*item))
   for x in edges:
    src=self.db.execute('SELECT kind FROM tkg_nodes WHERE tenant=? AND id=?',(e.tenant,x['src'])).fetchone()
    dst=self.db.execute('SELECT kind FROM tkg_nodes WHERE tenant=? AND id=?',(e.tenant,x['dst'])).fetchone()
    if not src or not dst:raise GapError('edge endpoint absent in tenant')
    if (src[0],dst[0]) not in ALLOWED[x['relation']]:raise GraphError('relation kind not allowed')
    prior=self.db.execute('SELECT src,dst,relation,source_event FROM tkg_edges WHERE tenant=? AND id=?',(e.tenant,x['id'])).fetchone()
    item=(x['src'],x['dst'],x['relation'],e.event_id)
    if prior and prior!=item:raise GraphError('edge collision')
    self.db.execute('INSERT OR IGNORE INTO tkg_edges VALUES(?,?,?,?,?,?)',(e.tenant,x['id'],*item))
   self.db.execute('INSERT INTO tkg_events VALUES(?,?,?,?,?)',(e.tenant,e.stream,e.sequence,e.event_id,h))
  return True

 def trace(self,tenant:str,start:str,depth:int=5,can_view=None)->dict:
  require_id(tenant);require_id(start)
  if type(depth) is not int or not 0<=depth<=8:raise GraphError('depth outside safety limit')
  if can_view is None:raise PermissionError('per-resource authorization callback required')
  visited=set(); queue=[(start,0)]; nodes=[];edges=[]
  while queue:
   ident,d=queue.pop(0)
   if ident in visited:continue
   found=self.db.execute('SELECT kind,source_ref,source_version,trust_state,payload FROM tkg_nodes WHERE tenant=? AND id=?',(tenant,ident)).fetchone()
   if not found or not can_view(tenant,ident,found[0]):continue
   visited.add(ident)
   nodes.append({'id':ident,'kind':found[0],'source_ref':found[1],'source_version':found[2],'trust_state':found[3],'payload':json.loads(found[4])})
   if d==depth:continue
   for edge_id,dst,rel,src_ev in self.db.execute('SELECT id,dst,relation,source_event FROM tkg_edges WHERE tenant=? AND src=? ORDER BY id',(tenant,ident)):
    child=self.db.execute('SELECT kind FROM tkg_nodes WHERE tenant=? AND id=?',(tenant,dst)).fetchone()
    if child and can_view(tenant,dst,child[0]):
     edges.append({'id':edge_id,'src':ident,'dst':dst,'relation':rel,'source_event':src_ev});queue.append((dst,d+1))
  result={'tenant':tenant,'nodes':sorted(nodes,key=lambda x:x['id']),'edges':sorted(edges,key=lambda x:x['id'])}
  result['projection_digest']=digest(result)
  return result

 def projection_digest(self,tenant:str)->str:
  require_id(tenant)
  n=self.db.execute('SELECT * FROM tkg_nodes WHERE tenant=? ORDER BY id',(tenant,)).fetchall()
  e=self.db.execute('SELECT * FROM tkg_edges WHERE tenant=? ORDER BY id',(tenant,)).fetchall()
  v=self.db.execute('SELECT * FROM tkg_events WHERE tenant=? ORDER BY stream,seq',(tenant,)).fetchall()
  return digest({'nodes':n,'edges':e,'events':v})
