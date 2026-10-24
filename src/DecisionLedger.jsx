import React,{useEffect,useMemo,useState} from 'react';
import {AlertTriangle,ArrowRight,BookOpen,CheckCircle2,ChevronRight,Copy,FileClock,FileSearch,Hash,RefreshCw,ShieldAlert} from 'lucide-react';
import {ledgerProjection,validateDecisionId} from './ledger-model.js';
import {readEnterpriseRecord} from './OperationsConsole.jsx';

const formatType=t=>t.replace(/^decision\./,'').replaceAll('_',' ');
export default function DecisionLedger({specPaths={},apiOnline=false}){
 const [decisionId,setDecisionId]=useState(''),[token,setToken]=useState(''),[busy,setBusy]=useState(false),[issue,setIssue]=useState(''),[record,setRecord]=useState(null),[selected,setSelected]=useState(0),[tab,setTab]=useState('detail');
 const supported=Boolean(specPaths?.['/v1/decision-events/{did}']?.get || specPaths?.['/v1/decision-events/{decision_id}']?.get);
 const selectedEvent=record?.events[selected]||null;
 const display=useMemo(()=>({total:record?.events.length??null,latest:record?.events.at(-1)?.type??null}),[record]);
 useEffect(()=>{setIssue('');setRecord(null);setSelected(0)},[decisionId]);
 async function load(){setBusy(true);setIssue('');setRecord(null);try{
  const id=validateDecisionId(decisionId);
  const response=await readEnterpriseRecord(`/v1/decision-events/${encodeURIComponent(id)}`,{token});
  const projected=ledgerProjection(response);
  if(projected.decisionId!==id)throw Error('Response decision ID mismatch');
  setRecord(projected);setSelected(Math.max(0,projected.events.length-1));
 }catch(err){setIssue(err instanceof Error?err.message:'Unable to load decision')}finally{setBusy(false)}}
 const integrity=record?.integrity==='LOCAL_HASH_CONSISTENT';
 return <section className="ledger-root">
  <div className="ledger-toolbar"><div><div className="eyebrow">ASSURANCE / DECISION INFRASTRUCTURE</div><h1>Decision Event Ledger</h1><p>Authoritative R7 replay · Independent attestation history · Read-only investigation</p></div><span className="ops-status">{apiOnline?'API online':'API offline'} · {supported?'R7 route available':'R7 route unavailable'}</span></div>
  <div className="ledger-filters"><label>Decision ID<input aria-label="Decision ID" placeholder="Enter real decision ID" value={decisionId} maxLength={128} onChange={e=>setDecisionId(e.target.value)} /></label><label>Authorized read-only token<input aria-label="Ledger bearer token" placeholder="Bearer identity token" type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}/></label><button className="primary" disabled={!apiOnline||!supported||busy} onClick={load}><RefreshCw size={15}/>{busy?'Loading…':'Load decision'}</button></div>
  {issue&&<div role="alert" className="ops-error"><AlertTriangle size={16}/>{issue}</div>}
  {!supported&&<div className="ledger-disclosure"><ShieldAlert size={18}/>The running API does not advertise the R7 GET contract. Review API registration; no sample record is substituted.</div>}
  {record?<>
   <div className="ledger-stats"><div><span>DECISION</span><strong>{record.decisionId}</strong></div><div><span>EVENTS</span><strong>{display.total}</strong></div><div><span>REPLAY STATUS</span><strong>{record.reviewStatus.toUpperCase()}</strong></div><div><span>INTEGRITY</span><strong className={integrity?'ledger-valid':'ledger-warning'}>{integrity?'Local hash consistent':record.integrity==='INTEGRITY_FAILED'?'Failed':'Not verified'}</strong></div></div>
   <div className="ledger-split"><aside className="ledger-timeline"><div className="ops-panel-title">EVENT TIMELINE <span>{record.events.length} records</span></div>{record.events.map((row,i)=><button key={`${row.seq}:${row.id}`} className={`ledger-event ${selected===i?'active':''}`} onClick={()=>{setSelected(i);setTab('detail')}}><span className="ledger-number">{String(row.seq).padStart(2,'0')}</span><span><b>{formatType(row.type)}</b><small>{row.actor} · {row.role}</small><small>{row.at||'Timestamp not supplied'}</small></span><ChevronRight size={15}/></button>)}{!record.events.length&&<div className="ops-empty">No ledger events returned.</div>}</aside>
    <div className="ledger-inspector"><div className="ops-panel-title">EVIDENCE INSPECTOR <span>Server-issued data, read only</span></div><div className="ledger-tabs" role="tablist" aria-label="Ledger inspector tabs">{['detail','snapshot','raw'].map(t=><button role="tab" aria-selected={tab===t} key={t} className={tab===t?'selected':''} onClick={()=>setTab(t)}>{t==='detail'?'Event details':t==='snapshot'?'Replay snapshot':'Raw response'}</button>)}</div>
     {tab==='detail'?(selectedEvent?<dl className="ledger-detail"><dt>Event type</dt><dd>{selectedEvent.type}</dd><dt>Sequence</dt><dd>{selectedEvent.seq}</dd><dt>Actor / role</dt><dd>{selectedEvent.actor} / {selectedEvent.role}</dd><dt>Recorded at</dt><dd>{selectedEvent.at||'Not supplied'}</dd><dt>Previous digest</dt><dd><code>{selectedEvent.previous||'Unavailable'}</code></dd><dt>Event digest</dt><dd><code>{selectedEvent.hash||'Unavailable'}</code></dd><dt>Event payload</dt><dd><pre className="ops-json">{JSON.stringify(selectedEvent.payload,null,2)}</pre></dd></dl>:<div className="ops-placeholder">Select an event.</div>):tab==='snapshot'?<div className="ledger-snapshot"><div className="ledger-kv">Evaluation version: <b>{record.version??'Unknown'}</b></div><div className="ledger-kv">Owner: <b>{record.owner??'Unknown'}</b></div><div className="ledger-kv">Independent reviewer: <b>{record.reviewer??'No reviewer recorded'}</b></div><div className="ledger-kv">Review time: <b>{record.reviewTime??'Not supplied'}</b></div><pre className="ops-json">{JSON.stringify(record.snapshot,null,2)}</pre></div>:<pre className="ops-json">{JSON.stringify(record.raw,null,2)}</pre>}
    </div></div>
   <div className="ledger-disclosure"><ShieldAlert size={18}/>{record.authority} Hash consistency is not external cryptographic anchoring or proof that source evidence is accurate.</div>
  </>:<div className="ledger-blank"><FileSearch size={30}/><h2>Select a decision to investigate</h2><p>Enter a real Decision OS identifier and an authorized bearer token. The page loads an existing event stream, reconstructs the recorded review state, and displays server-issued verification. It never invents approvals.</p><span>Need the ID? Use the existing Streamlit Decision Ledger to find an authorized decision. Server-side list/search is the next API contract.</span></div>}
 </section>
}
