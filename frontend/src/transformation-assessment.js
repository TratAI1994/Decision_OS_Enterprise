/** Deterministic advisory assessment. Never an authority for approvals. */
export const CAPABILITIES=Object.freeze([
 {id:'strategy',name:'Strategy and value',next:'Link AI opportunities to measurable business objectives',weight:3},
 {id:'data',name:'Data readiness',next:'Validate data lineage, access and quality',weight:3},
 {id:'risk',name:'Risk and compliance',next:'Establish applicable controls, owners and risk review',weight:3},
 {id:'architecture',name:'Architecture',next:'Evaluate fit-for-purpose cloud and on-prem patterns',weight:2},
 {id:'delivery',name:'Engineering delivery',next:'Implement reproducible CI, tests and supply-chain evidence',weight:2},
 {id:'people',name:'People and adoption',next:'Create adoption baseline and change-management plan',weight:2},
 {id:'operations',name:'Operations and reliability',next:'Measure telemetry, incidents and restore capabilities',weight:2},
 {id:'finance',name:'Financial assurance',next:'Agree benefit methods and independent Finance review',weight:3}
]);
export const OBJECTIVES=Object.freeze([
 {id:'quality',title:'Quality and compliance',focus:['risk','data','delivery'],frameworks:['Risk assessment','Business impact analysis','Theory of Constraints']},
 {id:'efficiency',title:'Cost and productivity',focus:['finance','operations','delivery'],frameworks:['Unit economics','Theory of Constraints','DCF sensitivity']},
 {id:'growth',title:'Revenue and customer growth',focus:['strategy','finance','data'],frameworks:['TAM / SAM / SOM','Customer lifetime value','Pricing and break-even']},
 {id:'modernization',title:'Platform modernization',focus:['architecture','delivery','operations'],frameworks:['Architecture trade-offs','Dependency analysis','Reliability assessment']},
 {id:'riskReduction',title:'Risk resilience',focus:['risk','operations','data'],frameworks:['PESTLE','Business impact analysis','Scenario analysis']}
]);
export function assessTransformation({scores,objective='quality'}={}){
 const target=OBJECTIVES.find(o=>o.id===objective);if(!target)throw Error('Unknown objective');
 if(!scores || typeof scores!=='object'||Array.isArray(scores))throw Error('Explicit maturity scores required');
 const missing=CAPABILITIES.filter(c=>!Object.prototype.hasOwnProperty.call(scores,c.id)).map(c=>c.id);
 if(missing.length) return {status:'INCOMPLETE',missing,actions:[],score:null,objective:target};
 let points=0,total=0;const actions=[];
 for(const c of CAPABILITIES){const n=scores[c.id];if(!Number.isInteger(n)||n<0||n>4)throw Error(`${c.id} must be an integer 0–4`);
 const importance=c.weight+(target.focus.includes(c.id)?2:0);points+=n*importance;total+=4*importance;
 if(n<3)actions.push({id:c.id,title:c.next,score:n,priority:(4-n)*importance});}
 actions.sort((a,b)=>b.priority-a.priority||a.id.localeCompare(b.id));
 return {status:'ASSESSED_SELF_REPORTED',score:Math.round(points/total*100),actions,missing:[],objective:target,limitations:'Self-reported maturity, advisory weighting; not certified or source-verified'};
}
