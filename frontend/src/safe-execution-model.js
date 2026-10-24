/** Pure, deterministic SAFe-inspired planning. NO approval, sync or evidence claims. */
import {validatePlan,optimizePortfolio,DEMO} from './portfolio-model.js';
export const TRAINS=[{id:'ART-1',name:'Enterprise AI Platform',teams:['Platform','Product'],iterations:5,capacity:45}];
export const DEMO_PI={id:'PI-SAMPLE',name:'Illustrative PI planning scenario',objectives:[{id:'PI-1',title:'Improve release assurance',plannedBV:8,actualBV:null,featureIds:['F-101','F-102'],owner:'Product Management'},{id:'PI-2',title:'Improve finance evidence readiness',plannedBV:5,actualBV:null,featureIds:['F-103'],owner:'Product Management'}],risks:[{id:'R-1',text:'Evidence collector readiness',status:'Open',owner:'RTE'},{id:'R-2',text:'Finance data access',status:'Mitigating',owner:'Business Owner'}],assignments:[{featureId:'F-101',iteration:1},{featureId:'F-102',iteration:3},{featureId:'F-103',iteration:4}]};
export function evaluatePI(items=DEMO.items,deps=DEMO.deps,pi=DEMO_PI){
 validatePlan(items,deps);
 const ids=new Set(items.map(f=>f.id));
 const features=new Map(items.map(f=>[f.id,f]));
 const assignments=new Map();
 for(const a of pi.assignments){
  if(!ids.has(a.featureId)||!Number.isInteger(a.iteration)||a.iteration<1||a.iteration>5||assignments.has(a.featureId))throw Error('Invalid or duplicate PI assignment');
  assignments.set(a.featureId,a.iteration);
 }
 const blockers=deps.filter(d=>assignments.has(d.to)&&(!assignments.has(d.from)||assignments.get(d.from)>assignments.get(d.to))).map(d=>({...d,reason:'Prerequisite absent or scheduled after dependent'}));
 const objectives=pi.objectives.map(o=>{
  if(!Array.isArray(o.featureIds)||o.featureIds.some(id=>!ids.has(id)))throw Error('Unknown objective feature');
  if(!Number.isFinite(o.plannedBV)||o.plannedBV<0||o.plannedBV>10)throw Error('Invalid planned business value');
  if(o.actualBV!==null && (!Number.isFinite(o.actualBV)||o.actualBV<0||o.actualBV>10))throw Error('Invalid actual business value');
  return {...o,coverage:o.featureIds.filter(id=>assignments.has(id)).length,plannedFeatures:o.featureIds.length};
 });
 const totalPlanned=objectives.reduce((n,o)=>n+o.plannedBV,0);
 const allActual=objectives.every(o=>o.actualBV!==null);
 const totalActual=allActual?objectives.reduce((n,o)=>n+o.actualBV,0):null;
 const predictability=allActual && totalPlanned>0?100*totalActual/totalPlanned:null;
 return {objectives,blockers,assignments:[...assignments].map(([featureId,iteration])=>({featureId,iteration,title:features.get(featureId).title,teamId:features.get(featureId).teamId})),totalPlanned,totalActual,predictability,hasActualEvidence:false};
}
export function inspectAllocation(items=DEMO.items,deps=DEMO.deps,{budget=95,buffer=.15,capacities=DEMO.teamCapacities}={}){
 const result=optimizePortfolio(items,deps,{budget,buffer,teamCapacities:capacities});
 const spent=result.cost;
 const byTeam=Object.entries(capacities).map(([team,capacity])=>({team,capacity,effective:Math.floor(capacity*(1-buffer)),used:items.filter(f=>result.selected.includes(f.id)&&f.teamId===team).reduce((s,f)=>s+f.size,0)}));
 return {...result,budget,spent,remaining:budget-spent,byTeam,algorithm:'Bounded exact subset search; max 20 features; score=Σ WSJF; illustrative only'};
}
