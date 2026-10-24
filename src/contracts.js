export const PHASES = Object.freeze([
 { id:'assess', name:'Assess', subtitle:'Current capabilities', help:'Capture your readiness baseline, source systems and accountable sponsor.', artifacts:['Maturity assessment','Data readiness','Risk register'] },
 { id:'strategize', name:'Strategize', subtitle:'Outcome-led priorities', help:'Select measurable enterprise AI opportunities and define the business case.', artifacts:['Target outcomes','Prioritization criteria','Sponsor approval'] },
 { id:'architect', name:'Architect', subtitle:'Design trade-offs', help:'Compare reference patterns, constraints, security and total cost.', artifacts:['HLD and LLD','Architecture decision','Threat model'] },
 { id:'plan', name:'Plan', subtitle:'Investment roadmap', help:'Map funding, dependencies, milestones, adoption and independent approval.', artifacts:['Portfolio roadmap','Expected value','Approval-time snapshot'] },
 { id:'execute', name:'Execute', subtitle:'Trusted engineering', help:'Attach source-backed build, tests, security scans and deployment evidence.', artifacts:['Git commit','CI run','SBOM','Deployment record'] },
 { id:'assure', name:'Assure', subtitle:'Control and replay', help:'Verify identity, signatures, nonce replay resistance, audit lineage and human authorization.', artifacts:['Evidence digest','Independent review','Audit replay'] },
 { id:'measure', name:'Measure', subtitle:'Realized outcomes', help:'Compare projected, observed and independently finance-attested value.', artifacts:['Measurement method','Finance attestation','Variance explanation'] },
 { id:'learn', name:'Learn', subtitle:'Improve safely', help:'Review evidence-qualified lessons and propose changes for human approval.', artifacts:['Retrospective','Verified outcomes','Action proposal'] }
]);
export const GRAPH_TYPES=Object.freeze(['Objective','Initiative','Risk','Architecture','Decision','Evidence','Deployment','Outcome','Finance']);
export const TRUST_CONTROLS=Object.freeze([
 {id:'ingestion',label:'Authenticated ingestion',how:'A signed submission returned AUTHENTICATED_COLLECTOR_CONTENT_MATCHED.',status:'DEMONSTRATED'},
 {id:'replay',label:'Duplicate nonce rejection',how:'Replay the byte-identical timestamp/nonce/signature; require HTTP 409.',status:'NOT_TESTED'},
 {id:'tamper',label:'Signed payload tampering',how:'Change bytes without generating a new signature; require rejection.',status:'NOT_TESTED'},
 {id:'tenant',label:'Cross-tenant isolation',how:'Use two separate tenant identities to prove cross-tenant GET is blocked.',status:'NOT_TESTED'},
 {id:'postgres',label:'PostgreSQL UPDATE / DELETE',how:'Only in a disposable test database, attempt forbidden row mutations.',status:'NOT_TESTED'},
 {id:'concurrency',label:'Concurrent nonce race',how:'Send two identical-nonce requests concurrently: one succeeds, one conflicts.',status:'NOT_TESTED'}
]);
export function summarizeReport(report) {
 if(!report || typeof report!=='object') return null;
 const checks=Array.isArray(report.checks)?report.checks:[];
 const counts={PASS:0,FAIL:0,NOT_TESTED:0,NOT_IMPLEMENTED:0};
 for(const entry of checks) if(Object.hasOwn(counts,entry.status))counts[entry.status]++;
 return {counts,certified:false,entries:checks}; // untrusted local report never confers platform certification
}
export function normalizedEndpoint(port){
 if(!/^\d{1,5}$/.test(String(port)))throw new Error('Invalid port');
 const n=Number(port);if(n<1||n>65535)throw new Error('Invalid port');
 return `http://127.0.0.1:${n}`;
}
