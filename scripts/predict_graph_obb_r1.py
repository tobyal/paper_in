"""Run the official predictor with only an opt-in low-cardinality OBB guard."""
import json,os,pathlib,sys
import numpy as np
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/relags_obb_repair_r1'
sys.path.insert(0,str(ROOT/'ReLaGS'))
import predict_3d_scene_graph as predictor
import relags_audit
from obb_boundary_r1 import wrap_official_obb
root_cause=json.loads((OUT/'00_investigation/metrics/root_cause.json').read_text())
assert root_cause['status']=='verified' and all(root_cause['checks'].values())
attempt=os.environ.get('RELAGS_ATTEMPT_ID','manual')
audit=OUT/'08_scene_graph/data'/attempt;audit.mkdir(parents=True,exist_ok=True)
records=[];call=0
official=predictor.get_oriented_bounding_boxes
def guarded(*args,**kwargs):
    global call
    level=predictor.LEVELS[call];call+=1
    start=len(records);result=wrap_official_obb(official,records)(*args,**kwargs)
    for r in records[start:]:r['level']=level
    checks=[]
    old=np.load(ROOT/f'outputs/relags_baseline/08_scene_graph/diagnostics/obb/level_{level}_valid_obbs.npz')
    for i,cid in enumerate(old['cluster_ids']):
        box=result[cid]
        checks.append(all(np.array_equal(box[k],old[key][i]) for k,key in enumerate(['centers','rotations','extents'])))
    assert all(checks),'An originally valid OBB changed'
    (audit/f'level_{level}_obb_validation.json').write_text(json.dumps({'level':level,'nodes':len(result),'unchanged_original_valid_boxes':len(checks),'all_valid_boxes_bitwise_equal':all(checks),'fallback_nodes':records[start:]},indent=2))
    return result
predictor.get_oriented_bounding_boxes=guarded
def save(stage,name,value):
    assert stage=='08_scene_graph'
    value=relags_audit.cpu(value)
    if name.endswith('_graph_inputs'):
        for key in ['centers','rotations','extents','node_geometry','node_language']:
            assert np.isfinite(np.asarray(value[key])).all(),key
        assert list(map(int,value['original_cluster_ids']))==list(range(len(value['original_cluster_ids'])))
    if name.endswith('_edge_predictions'):
        for key in ['edge_features','relation_similarities']:assert torch.isfinite(value[key]).all(),key
    torch.save(value,audit/(name+'.pt'))
    (audit.parent/'audit_latest.json').write_text(json.dumps({'attempt':attempt,'directory':str(audit)},indent=2))
relags_audit.save=save
predictor.main()
assert len(records)==5 and {r['cluster_id'] for r in records}=={1822,1836,1927,1987,2307}
(OUT/'08_scene_graph/metrics/obb_repair.json').write_text(json.dumps({'status':'completed','fallbacks':records,'all_original_nodes_preserved':True,'all_original_valid_boxes_bitwise_equal':True,'core_predictor':'unmodified except runtime binding for degenerate OBB geometry and serialization destination','audit':str(audit)},indent=2))
print('R1 prediction complete; all nodes retained; exactly five OBB boundary cases',flush=True)
