import {validatePlan, analyzePortfolio} from './portfolio-model.js';
import {evaluatePI} from './safe-execution-model.js';

export function programBoard(items,deps,pi,iterations=5){
 validatePlan(items,deps);
 if(!Number.isInteger(iterations)||iterations<1||iterations>20)throw Error('Invalid iteration count');
 const result=evaluatePI(items,deps,pi);
 const byId=new Map(items.map(x=>[x.id,x]));
 const nodes=result.assignments.map(a=>({...a,objectiveId:byId.get(a.featureId).objectiveId,epicId:byId.get(a.featureId).epicId}));
 const locations=new Map();
 for(let iteration=1;iteration<=iterations;iteration++){
  const column=nodes.filter(a=>a.iteration===iteration).sort((a,b)=>a.featureId.localeCompare(b.featureId));
  column.forEach((a,row)=>locations.set(a.featureId,{x:(iteration-1)*214+106,y:row*100+80,iteration}));
 }
 const links=deps.map(d=>({ ...d,fromPoint:locations.get(d.from)||null,toPoint:locations.get(d.to)||null,
  state:!locations.has(d.from)||!locations.has(d.to)?'UNSCHEDULED':locations.get(d.from).iteration>locations.get(d.to).iteration?'BLOCKED':'ORDERED'}));
 return {nodes,links,locations,iterations,blockers:links.filter(x=>x.state!=='ORDERED'),height:Math.max(300,Math.max(...[...locations.values()].map(p=>p.y),0)+85)};
}
export function planningIndicators(items,deps,pi,capacities){
 const evaluated=evaluatePI(items,deps,pi);
 const allocated=evaluated.assignments.reduce((n,a)=>n+(items.find(x=>x.id===a.featureId)?.size||0),0);
 const capacity=Object.values(capacities).reduce((a,b)=>a+b,0)*pi?.capacityFactor || Object.values(capacities).reduce((a,b)=>a+b,0);
 if(!Number.isFinite(capacity)||capacity<0)throw Error('Invalid capacity');
 return {plannedPoints:allocated,capacityPoints:capacity,plannedUtilizationPct:capacity>0?100*allocated/capacity:null,
  objectiveCoverage:evaluated.objectives.length?evaluated.objectives.filter(o=>o.coverage===o.plannedFeatures).length/evaluated.objectives.length*100:null,
  unaligned:analyzePortfolio(items,deps).orphaned.length,dependencyBlockers:evaluated.blockers.length,
  actualPredictabilityPct:null,actualFlowVelocity:null,actualFlowEfficiencyPct:null};
}
export function relationshipIndex(items,deps){
 validatePlan(items,deps);
 const rows=items.map(f=>({id:f.id,title:f.title,objective:f.objectiveId||null,initiative:f.objectiveId?'FOCUS-'+f.objectiveId:null,epic:f.epicId||null,team:f.teamId||null,dependencies:deps.filter(d=>d.to===f.id).map(d=>d.from),unlinked:!(f.objectiveId&&f.epicId)}));
 return rows;
}
export function answerPortfolioQuestion(question,items,deps,pi){
 const q=String(question||'').trim().toLowerCase();
 if(!q)return {answer:'Enter a question about the loaded plan.',records:[],classification:'NO_QUERY'};
 const rows=relationshipIndex(items,deps);
 const model=evaluatePI(items,deps,pi);
 const terms=q.match(/[a-z0-9-]+/g)||[];
 if(/delay|block|depend|critical/.test(q)){
  return {answer:`${model.blockers.length} sequencing dependency blocker(s) in this illustrative PI plan. This does not establish actual delivery delays.`,records:model.blockers.map(x=>`${x.from} → ${x.to}`),classification:'PLANNING_ONLY'};
 }
 if(/orphan|unalign|strategy/.test(q)){
  const subset=rows.filter(r=>r.unlinked);
  return {answer:`${subset.length} feature(s) lack an objective or epic relationship in the loaded plan.`,records:subset.map(r=>r.id),classification:'PLANNING_ONLY'};
 }
 if(/risk|art|team|capacity/.test(q)){
  const teams=[...new Set(rows.map(r=>r.team).filter(Boolean))];
  return {answer:`${teams.length} team(s) referenced by the loaded illustrative plan. An actual highest-risk ART cannot be determined without validated risk and delivery observations.`,records:teams,classification:'INSUFFICIENT_EVIDENCE'};
 }
 if(/roi|finance|sap|production|verified/.test(q))return {answer:'Insufficient authoritative source data to answer this financial, application, or production question. Connect decision, finance and deployment records first.',records:[],classification:'INSUFFICIENT_EVIDENCE'};
 const matched=rows.filter(r=>terms.some(t=>t.length>2&&(`${r.id} ${r.title} ${r.team} ${r.epic}`).toLowerCase().includes(t)));
 return {answer:matched.length?`${matched.length} matching feature(s) in the illustrative plan.`:'No matching records in this local plan; this is not an enterprise-wide search.',records:matched.map(r=>r.id),classification:'PLANNING_ONLY'};
}
