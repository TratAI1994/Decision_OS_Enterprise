export async function getOpenApi(signal){
 const res=await fetch('/api/openapi.json',{method:'GET',signal,credentials:'omit',headers:{Accept:'application/json'}});
 if(!res.ok)throw new Error(`API responded HTTP ${res.status}`);
 return res.json();
}
export function routeAvailable(spec,path,method){return !!(spec?.paths?.[path]?.[method.toLowerCase()]);}
