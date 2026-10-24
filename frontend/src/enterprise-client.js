import {validateIdentifier} from './enterprise-domain.js';
export class ApiReadError extends Error { constructor(status, message, requestId=''){super(message);this.name='ApiReadError';this.status=status;this.requestId=requestId;} }
export async function readBoundedRecord(kind,id,{token='',signal}={}){
 const paths={outcome:'/v1/outcome-economics/',risk:'/v1/decision-events/',source:'/v1/source-evidence/',decision:'/v1/decision-events/'};
 if(!Object.prototype.hasOwnProperty.call(paths,kind))throw Error('Unsupported read contract');
 const record=validateIdentifier(id);
 const headers={Accept:'application/json'};
 if(token)headers.Authorization=`Bearer ${token}`;
 const response=await fetch('/api'+paths[kind]+encodeURIComponent(record),{method:'GET',headers,credentials:'omit',signal});
 const requestId=response.headers?.get?.('x-request-id')||'';
 const raw=await response.text();let obj;try{obj=JSON.parse(raw)}catch{obj=null}
 if(!response.ok){const reason=({401:'Unauthenticated',403:'Forbidden by server policy',404:'Record or route not found',409:'Integrity or concurrency conflict',422:'Invalid request'}[response.status]||'Request failed');throw new ApiReadError(response.status,reason,requestId)}
 if(!obj||typeof obj!=='object')throw new Error('Backend returned invalid JSON');
 return {data:obj,requestId};
}
