// Pure defensive projections. These functions never grant authorization or change trust state.
export const ID_PATTERN = /^[A-Za-z0-9_.:-]{1,128}$/;
export function validateIdentifier(value) { const id = String(value ?? '').trim(); if (!ID_PATTERN.test(id)) throw new Error('Use a valid record ID (1–128 letters, digits, _, -, ., :)'); return id; }
export function moneyText(value, code='USD') { if(value===null||value===undefined||value==='')return 'Not verified'; if(!/^[A-Z]{3}$/.test(code)) return String(value); const n=Number(value); return Number.isFinite(n)?new Intl.NumberFormat('en-US',{style:'currency',currency:code}).format(n):String(value); }
export function outcomeProjection(record){
 if(!record || typeof record!=='object' || !record.summary || !record.integrity)throw new Error('Malformed Outcome Economics response');
 const s=record.summary;
 return {status:s.status||'unknown',period:s.period||'Not recorded',currency:s.currency||'USD',expected:s.expected??null,reported:s.self_reported??null,attested:s.finance_verified??null,variance:s.variance??null,reviewer:s.finance_reviewer||null,attribution:s.attribution||'unknown',integrity:record.integrity.consistent===true?'CONSISTENT':record.integrity.consistent===false?'INVALID':'UNKNOWN',events:Array.isArray(record.events)?record.events:[],source:s.finance_source_ref||s.source_ref||null,disclosure:record.disclosure||''};
}
export function riskProjection(record){
 if(!record || typeof record!=='object')throw Error('Malformed risk record');
 const raw=record.snapshot?.kill_criteria??record.snapshot?.baseline?.kill_criteria??record.state?.kill_criteria??record.state?.baseline?.kill_criteria??[];
 return {criteria:Array.isArray(raw)?raw:[],integrity:record.verification?.valid??record.integrity?.consistent??null,state:record.state||{},audit:Array.isArray(record.events)?record.events:[]};
}
export function sourceEvidenceProjection(record){
 if(!record || typeof record!=='object'|| !record.id)throw Error('Malformed source evidence response');
 return {id:String(record.id),tenant:String(record.tenant_id||''),source:String(record.source_system||''),hash:String(record.content_sha256||''),trust:String(record.trust_state||'UNKNOWN'),businessVerified:record.business_validated===true,anchored:record.external_anchor_verified===true,record:record};
}
export function evidenceCoverage(stage){const names=['Git commit','CI pipeline run','Test results','Security scans','SBOM','Artifact signature','Deployment approval','Production telemetry'];const found=Array.isArray(stage?.verified_links)?stage.verified_links:[];return names.map(n=>({name:n,status:found.includes(n)?'SOURCE LINK PRESENT':'NOT CONNECTED'}));}
export function transformationLinks({objective,initiative,risk,decision,evidence,deployment,outcome,finance}={}){return [objective,initiative,risk,decision,evidence,deployment,outcome,finance].map((id,index)=>({type:['Objective','Initiative','Risk','Decision','Evidence','Deployment','Outcome','Finance'][index],id:id?String(id):null,status:id?'REFERENCE ENTERED — NOT VERIFIED':'NOT LINKED'}));}
