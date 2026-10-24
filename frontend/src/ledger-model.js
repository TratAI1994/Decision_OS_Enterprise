/** Pure, defensive projection of R7 decision-event history. No trust promotion. */
export function validateDecisionId(value) {
 const id=String(value??'').trim();
 if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(id)) throw new Error('Enter a valid decision ID (letters, numbers, _, -, :, .)');
 return id;
}
export function ledgerProjection(payload) {
 if (!payload || typeof payload!=='object' || Array.isArray(payload) || !Array.isArray(payload.events)) throw Error('Unexpected ledger response');
 const decisionId=validateDecisionId(payload.decision_id);
 const events=payload.events.map((row,index)=>{
  if (!row || typeof row!=='object' || Array.isArray(row)) throw Error('Invalid ledger event');
  const seq=Number(row.seq);
  if (!Number.isSafeInteger(seq)||seq!==index+1) throw Error('Nonconsecutive sequence in ledger response');
  return {seq,id:String(row.id||''),type:String(row.event_type||'unknown'),actor:String(row.actor_id||'unknown'),role:String(row.role||'unknown'),at:String(row.timestamp||''),hash:String(row.event_hash||''),previous:String(row.prev_hash||''),payload:row.payload??null};
 });
 const integrity=payload.verification?.valid===true?'LOCAL_HASH_CONSISTENT':payload.verification?.valid===false?'INTEGRITY_FAILED':'NOT_VERIFIED';
 return {decisionId,events,integrity,reviewStatus:String(payload.state?.status||'unknown'),version:payload.state?.version??null,owner:payload.state?.owner_id??null,reviewer:payload.state?.approved_by??null,reviewTime:payload.state?.approved_at??null,snapshot:payload.state?.snapshot??null,authority:payload.authority||'Local event integrity is not external anchoring or funding approval.',raw:payload};
}
export function isAuthoritativelySigned(projection){return false;} // R7 offers no external signature proof
