import React, { useMemo, useState } from 'react';
import { AlertTriangle, ArrowUpRight, ClipboardList, Database, FileCode2, Fingerprint, RefreshCw, ShieldCheck, Waypoints } from 'lucide-react';

export const OPERATIONS = Object.freeze([
 {id:'ledger',title:'Decision Ledger',icon:'ledger',prefixes:['/v1/decision-events','/v1/decision-evaluation','/v1/decisions'],route:'/v1/decision-events/{decision_id}',placeholder:'Decision ID',purpose:'Event reconstruction, amendments, attestations, decision history',legacy:'Decision Ledger'},
 {id:'economics',title:'Outcome Economics',icon:'finance',prefixes:['/v1/outcome','/v1/benefit'],route:'',placeholder:'Record ID',purpose:'Expected, reported and finance-attested benefit reconciliation',legacy:'Outcome Economics'},
 {id:'risk',title:'Risk & Controls',icon:'risk',prefixes:['/v1/kill-window','/v1/trust','/v1/decision-events'],route:'',placeholder:'Decision ID',purpose:'Frozen criteria, risk lineage, evidence and human review',legacy:'Kill-Window Assurance'},
 {id:'pipelines',title:'DevSecOps & AIOps',icon:'pipeline',prefixes:['/v1/source-evidence'],route:'/v1/source-evidence/{evidence_id}',placeholder:'Evidence ID',purpose:'Authenticated CI evidence, stage results and operational diagnostic context',legacy:'DevSecOps Pipeline Studio'},
 {id:'assurance',title:'Trust & Audit',icon:'trust',prefixes:['/v1/source-evidence','/v1/decision-events','/v1/trust'],route:'/v1/source-evidence/{evidence_id}',placeholder:'Evidence ID',purpose:'Source-bound evidence inspection, audit replay and trust distinctions',legacy:'Trust & Audit'},
]);

export function matchingReadRoutes(paths, group) {
 if (!paths || typeof paths!=='object') return [];
 return Object.entries(paths).filter(([path,ops]) => group.prefixes.some(prefix=>path.startsWith(prefix)) && ops && typeof ops==='object' && 'get' in ops).map(([path])=>path).sort();
}
export function safeReadPath(path, id) {
 if (!path || !path.startsWith('/v1/') || !/^\/v1\/[a-zA-Z0-9_{}\/-]+$/.test(path)) throw Error('Unsupported API route');
 if ((path.match(/\{/g)||[]).length > 1) throw Error('This route needs multiple identifiers; use the legacy workspace');
 if (path.includes('{')) {
  if (!id?.trim() || !/^[A-Za-z0-9_.:-]{1,128}$/.test(id.trim())) throw Error('Enter a valid record ID (letters, numbers, _, -, : or .)');
  return path.replace(/\{[a-zA-Z0-9_]+\}/,encodeURIComponent(id.trim()));
 }
 return path;
}
export async function readEnterpriseRecord(path,{token='',signal}={}) {
 const headers={Accept:'application/json'};
 if (token) headers.Authorization=`Bearer ${token}`;
 const res=await fetch(`/api${path}`,{method:'GET',headers,credentials:'omit',signal});
 const text=await res.text();
 let data;try{data=JSON.parse(text)}catch{data={error:'Non-JSON API response'}};
 if(!res.ok)throw Error(`HTTP ${res.status}: ${typeof data.detail==='string'?data.detail:res.statusText}`);
 return data;
}
function treeText(value){return JSON.stringify(value,null,2)}
export default function OperationsConsole({groupId='ledger',specPaths={},apiOnline=false}){
 const group=OPERATIONS.find(x=>x.id===groupId)||OPERATIONS[0];
 const routes=useMemo(()=>matchingReadRoutes(specPaths,group),[specPaths,groupId]);
 const [selection,setSelection]=useState('');
 const route=routes.includes(selection)?selection:routes.includes(group.route)?group.route:(routes[0]||'');
 const [recordId,setRecordId]=useState('');const [token,setToken]=useState('');const [response,setResponse]=useState(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const [showJson,setShowJson]=useState(true);
 async function load(){
  setBusy(true);setError('');setResponse(null);
  try{const path=safeReadPath(route,recordId);const json=await readEnterpriseRecord(path,{token});setResponse({path,data:json});}
  catch(e){setError(e.message)}finally{setBusy(false)}
 }
 return <section className="ops-console">
  <div className="ops-heading"><div><div className="eyebrow">ENTERPRISE / OPERATIONS</div><h1>{group.title}</h1><p>{group.purpose}</p></div><span className="ops-status">{apiOnline?'API reachable':'API unavailable'}</span></div>
  <div className="ops-layout">
   <aside className="ops-list"><div className="ops-panel-title">WORKSPACE EXPLORER <span>{routes.length} GET routes</span></div>
     {routes.length?routes.map(item=><button className={`ops-route ${route===item?'active':''}`} key={item} onClick={()=>{setSelection(item);setResponse(null);setError('')}}><Database size={15}/><span>{item}</span></button>):<div className="ops-empty"><AlertTriangle size={17}/> No compatible backend GET endpoints advertised. Do not mistake this for missing data.</div>}
     <div className="ops-list-bottom"><b>Existing workspace</b><p>Full workflows remain in Streamlit until feature-parity tests pass.</p><a href="http://127.0.0.1:8502" target="_blank" rel="noopener noreferrer">Open Streamlit <ArrowUpRight size={13}/></a></div>
   </aside>
   <div className="ops-content"><div className="ops-panel-title">RECORD INSPECTOR <span>Read only · Tenant controls enforced by API</span></div>
     <div className="ops-fields"><label>API endpoint<select aria-label="GET endpoint" value={route} onChange={e=>{setSelection(e.target.value);setResponse(null)}} disabled={!routes.length}>{routes.length?routes.map(x=><option key={x}>{x}</option>):<option value="">No available route</option>}</select></label><label>{group.placeholder}<input aria-label="Record identifier" value={recordId} onChange={e=>setRecordId(e.target.value)} placeholder={group.placeholder}/></label></div>
     <div className="ops-fields"><label>Authorized API bearer token <span className="ops-subtle">(optional; held in page memory only)</span><input aria-label="Bearer token" type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} placeholder="Do not use collector signing secrets"/></label></div>
     <div className="ops-actions"><button className="primary" disabled={!route||busy||!apiOnline} onClick={load}><RefreshCw size={15}/>{busy?'Loading…':'Load authenticated record'}</button><button className="secondary" disabled={!response} onClick={()=>setShowJson(v=>!v)}>{showJson?'Hide':'Show'} JSON</button></div>
     {error&&<div role="alert" className="ops-error"><AlertTriangle size={16}/>{error}</div>}
     {response?<><div className="ops-record-meta"><ShieldCheck size={16}/><span>Response returned by the API. Trust claims depend on server evidence and must not be inferred from HTTP 200.</span></div><div className="ops-record-path">GET {response.path}</div>{showJson&&<pre className="ops-json">{treeText(response.data)}</pre>}</>:<div className="ops-placeholder"><ClipboardList size={24}/><strong>No record selected</strong><p>Choose an available backend route and load a real record. No fictional decisions, risk scores or financial outcomes are generated.</p></div>}
   </div>
  </div>
 </section>
}
