export function validatePlan(items, dependencies = []) {
  if (!Array.isArray(items) || !Array.isArray(dependencies)) throw new Error('Items and dependencies must be arrays');
  const ids = new Set();
  for (const f of items) {
    if (!f || typeof f.id !== 'string' || !f.id || ids.has(f.id)) throw new Error('Feature IDs must be nonempty and unique');
    ids.add(f.id);
    for (const k of ['value','criticality','riskReduction','size','cost']) if (!Number.isFinite(f[k]) || f[k] < 0) throw new Error(`${f.id}: invalid ${k}`);
    if (f.size === 0) throw new Error(`${f.id}: size must be greater than zero`);
  }
  const graph = new Map(items.map(x => [x.id, []]));
  for (const d of dependencies) {
    if (!ids.has(d.from) || !ids.has(d.to) || d.from === d.to) throw new Error('Invalid dependency reference');
    graph.get(d.from).push(d.to);
  }
  const active = new Set(), visited = new Set(), order = [];
  function dfs(v) { if (active.has(v)) throw new Error('Dependency cycle'); if (visited.has(v)) return; active.add(v); for (const x of graph.get(v)) dfs(x); active.delete(v); visited.add(v); order.push(v); }
  for (const id of ids) dfs(id);
  return {order:order.reverse()};
}
export function scoreWSJF(f) { return (f.value+f.criticality+f.riskReduction)/f.size; }
export function analyzePortfolio(items,deps=[]) {
  validatePlan(items,deps);
  const orphaned=items.filter(f=>!f.epicId || !f.objectiveId);
  return {total:items.length, orphaned, aligned:items.length-orphaned.length, rankings:[...items].map(f=>({...f,wsjf:scoreWSJF(f)})).sort((a,b)=>b.wsjf-a.wsjf||a.id.localeCompare(b.id))};
}
export function optimizePortfolio(items,deps=[],opts={}) {
  validatePlan(items,deps);
  if(items.length>20) throw new Error('Exact planner limited to 20 features; use a server-side MILP for larger portfolios');
  const budget=Number(opts.budget),buffer=Number(opts.buffer ?? 0);
  if(!Number.isFinite(budget)||budget<0||!Number.isFinite(buffer)||buffer<0||buffer>=1) throw new Error('Invalid planning parameters');
  const caps=opts.teamCapacities||{};
  if(Object.values(caps).some(c=>!Number.isFinite(c)||c<0)) throw new Error('Invalid team capacity');
  const prerequisites=new Map(items.map(f=>[f.id,[]]));
  for(const d of deps) prerequisites.get(d.to).push(d.from);
  let best={value:-Infinity,selected:[],cost:0};
  const n=items.length;
  function run(i,chosen,cost,used,value) {
    if(i===n){
      const s=new Set(chosen);
      if(chosen.some(id=>prerequisites.get(id).some(x=>!s.has(x)))) return;
      const sorted=[...chosen].sort();
      if(value>best.value+1e-9 || (Math.abs(value-best.value)<1e-9 && sorted.join(',')<best.selected.join(','))) best={value,selected:sorted,cost};
      return;
    }
    const f=items[i];
    run(i+1,chosen,cost,used,value);
    if(opts.excludeOrphans!==false&&(!f.objectiveId||!f.epicId)) return;
    const limit=caps[f.teamId];
    const next=(used[f.teamId]||0)+f.size;
    if(cost+f.cost>budget || (limit!==undefined && next>Math.floor(limit*(1-buffer)))) return;
    run(i+1,[...chosen,f.id],cost+f.cost,{...used,[f.teamId]:next},value+scoreWSJF(f));
  }
  run(0,[],0,{},0);
  return {...best, status:'OPTIMAL_FOR_BOUNDED_INPUT', evaluatedCount:n, assumptions:'Illustrative WSJF utility; not approved funding or delivery forecast'};
}
export const DEMO={objective:'Reduce AI release lead time',items:[
{id:'F-101',title:'Signed build provenance',objectiveId:'OBJ-1',epicId:'E-1',teamId:'Platform',value:13,criticality:20,riskReduction:20,size:8,cost:32},
{id:'F-102',title:'Deployment evidence collector',objectiveId:'OBJ-1',epicId:'E-1',teamId:'Platform',value:13,criticality:13,riskReduction:20,size:13,cost:44},
{id:'F-103',title:'Finance impact dashboard',objectiveId:'OBJ-1',epicId:'E-2',teamId:'Product',value:13,criticality:8,riskReduction:8,size:8,cost:30},
{id:'F-104',title:'Legacy theme customization',objectiveId:null,epicId:null,teamId:'Product',value:2,criticality:1,riskReduction:1,size:13,cost:18}],deps:[{from:'F-101',to:'F-102'}],teamCapacities:{Platform:25,Product:20}};
