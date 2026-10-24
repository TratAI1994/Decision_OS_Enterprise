import sys,sqlite3,pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.transformation_graph import GraphProjection,SourceEvent,GraphError,GapError,digest
from backend.transformation_journey import Journey,STEPS

def ev(t='alpha',seq=1, nodes=None,edges=None):
 return SourceEvent(t,'R7',seq,'event-'+str(seq),'2026-10-23T10:00:00Z',tuple(nodes or ()),tuple(edges or ()), '0'*64)
def node(ident,kind,trust='CLAIM'):
 return {'id':ident,'kind':kind,'source_ref':'source-'+ident,'source_version':'1','trust_state':trust,'payload':{}}
def edge(ident,src,dst,rel):return {'id':ident,'src':src,'dst':dst,'relation':rel}
def graph():return GraphProjection(sqlite3.connect(':memory:'))
def allow(t,i,k):return True

def test_journey_all_steps():assert tuple(x['step'] for x in Journey('Pharma & Life Sciences','AWS CAF','Reduce defects').checklist())==STEPS
def test_journey_rejects_unknown():
 with pytest.raises(ValueError):Journey('Unknown','AWS CAF','Reduce defects')
def test_default_no_completed_steps():assert all(x['status']=='NOT_ASSESSED' for x in Journey('Cross-industry','Vendor neutral','Improve quality').checklist())
def test_snapshot_risk_trace():
 g=graph(); n=[node('i','INITIATIVE'),node('r','RISK'),node('d','DECISION'),node('e','EVIDENCE')]
 edges=[edge('ir','i','r','HAS_RISK'),edge('dr','d','r','MITIGATES'),edge('re','r','e','SUPPORTED_BY')]
 assert g.apply(ev(nodes=n,edges=edges))
 assert [v['id'] for v in g.trace('alpha','i',can_view=allow)['nodes']]==['e','i','r']
 assert len(g.trace('alpha','d',can_view=allow)['edges'])==2
def test_exact_retry_idempotent():
 g=graph();e=ev(nodes=[node('a','OBJECTIVE')]);assert g.apply(e);assert not g.apply(e)
def test_conflict_same_sequence():
 g=graph();g.apply(ev(nodes=[node('a','OBJECTIVE')]))
 with pytest.raises(GraphError):g.apply(ev(nodes=[node('b','OBJECTIVE')]))
def test_out_of_order_rejected():
 with pytest.raises(GapError):graph().apply(ev(seq=2))
def test_failed_transaction_no_partial_writes():
 g=graph()
 with pytest.raises(GapError):g.apply(ev(nodes=[node('a','OBJECTIVE')],edges=[edge('bad','a','missing','ADVANCES')]))
 assert g.db.execute('SELECT count(*) FROM tkg_nodes').fetchone()[0]==0
 assert g.db.execute('SELECT count(*) FROM tkg_events').fetchone()[0]==0
def test_cross_tenant_no_enumeration():
 g=graph();g.apply(ev(nodes=[node('private','EVIDENCE')]))
 assert g.trace('beta','private',can_view=allow)['nodes']==[]
def test_acl_per_resource_no_edges():
 g=graph();g.apply(ev(nodes=[node('i','INITIATIVE'),node('o','OBJECTIVE')],edges=[edge('e','i','o','ADVANCES')]))
 out=g.trace('alpha','i',can_view=lambda t,i,k:i=='i');assert len(out['nodes'])==1 and not out['edges']
def test_trace_requires_acl():
 with pytest.raises(PermissionError):graph().trace('alpha','i')
def test_unknown_node_kind():
 with pytest.raises(GraphError):graph().apply(ev(nodes=[node('x','MAGIC')]))
def test_invalid_relation_types():
 g=graph()
 with pytest.raises(GraphError):g.apply(ev(nodes=[node('i','INITIATIVE'),node('e','EVIDENCE')],edges=[edge('bad','i','e','ADVANCES')]))
def test_replay_digest_deterministic():
 e=ev(nodes=[node('i','INITIATIVE'),node('o','OBJECTIVE')],edges=[edge('e','i','o','ADVANCES')]);a=graph();b=graph();a.apply(e);b.apply(e)
 assert a.projection_digest('alpha')==b.projection_digest('alpha')
def test_reject_naive_timestamp():
 with pytest.raises(GraphError):SourceEvent('alpha','r',1,'id','2026-10-23T10:00:00',(),(), '0'*64)
def test_collision_rollback():
 g=graph();g.apply(ev(nodes=[node('a','OBJECTIVE')]))
 with pytest.raises(GraphError):g.apply(ev(seq=2,nodes=[node('a','RISK')]))
 assert g.db.execute('SELECT COUNT(*) FROM tkg_events').fetchone()[0]==1
def test_finance_trust_does_not_escalate():
 g=graph();g.apply(ev(nodes=[node('f','FINANCE_RECONCILIATION','OBSERVED')]))
 assert g.trace('alpha','f',can_view=allow)['nodes'][0]['trust_state']=='OBSERVED'
def test_depth_bounded():
 with pytest.raises(GraphError):graph().trace('alpha','x',depth=100,can_view=allow)
def test_cross_tenant_edges_fail():
 g=graph();g.apply(ev(t='other',nodes=[node('out','OBJECTIVE')]))
 with pytest.raises(GapError):g.apply(ev(nodes=[node('i','INITIATIVE')],edges=[edge('bad','i','out','ADVANCES')]))
