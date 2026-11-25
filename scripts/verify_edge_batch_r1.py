"""Verify official edge batching on real data for the pinned one-layer GNN."""
import json,pathlib,sys
import numpy as np
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ReLaGS'))
from predict_3d_scene_graph import load_model,NUM_LAYERS,REL_NAMES
from scene_graph.network_utils import get_edge_geom_features
from relags_relationships import load_relationship_embeddings
OUT=ROOT/'outputs/relags_obb_repair_r1'
model=load_model(str(ROOT/'models/relags/graph_transformer_512_80.pth'))
assert NUM_LAYERS==1 and len(model.graph_transformer_layers)==1 and not model.training
rels,_=load_relationship_embeddings(REL_NAMES);rels=rels.cuda()
sources=[(3,ROOT/'outputs/relags_baseline/08_scene_graph/data/20261125T004930Z_predict_root_diagnostic/level_3_graph_inputs.pt'),(2,OUT/'08_scene_graph/data/20261125T014029Z_predict_full_graph/level_2_graph_inputs.pt')]
rows=[]
for level,path in sources:
    d=torch.load(path,map_location='cpu');idx=np.asarray(d['edge_index']);selected=np.arange(idx.shape[1])
    if level==2:
        incident=np.flatnonzero(np.isin(idx,[1822,1836,1927,1987,2307]).any(axis=0))
        selected=np.unique(np.r_[np.arange(min(200000,idx.shape[1])),incident])
    edge=torch.tensor(idx[:,selected],device='cuda',dtype=torch.long)
    centers=d['centers'].cuda();rot=d['rotations'].cuda();ext=d['extents'].cuda()
    geometry=get_edge_geom_features(centers,rot,ext,edge).float()
    node_geo=d['node_geometry'].cuda();node_lang=d['node_language'].cuda()
    def compute(batch):
        outputs=[]
        with torch.no_grad():
            for start in range(0,edge.shape[1],batch):
                e=edge[:,start:start+batch];geo=geometry[start:start+batch]
                y=model(e,torch.zeros((e.shape[1],512),device='cuda'),geo,node_lang,node_geo)
                outputs.append(y.cpu())
        return torch.cat(outputs)
    full=compute(edge.shape[1]);torch.cuda.empty_cache();chunked=compute(100000)
    delta=(full-chunked).abs();a=(full@rels.cpu().T).argmax(1);b=(chunked@rels.cpu().T).argmax(1)
    row={'level':level,'edges_compared':edge.shape[1],'chunk_size':100000,'max_abs_feature_difference':delta.max().item(),'mean_abs_feature_difference':delta.mean().item(),'top1_relation_agreement':(a==b).float().mean().item(),'full_and_chunked_finite':bool(torch.isfinite(full).all() and torch.isfinite(chunked).all())}
    assert row['full_and_chunked_finite'] and row['max_abs_feature_difference']<1e-5
    assert torch.equal(a,b), 'Batching changed a top-1 relation on validation edges'
    rows.append(row);print(json.dumps(row),flush=True)
    np.savez_compressed(OUT/'00_investigation/data'/f'edge_batch_validation_level_{level}.npz',edge_indices=selected,per_edge_max_abs_error=delta.max(1).values.numpy(),full_top1=a.numpy(),chunked_top1=b.numpy())
    del full,chunked,delta,edge,geometry,d;torch.cuda.empty_cache()
(OUT/'00_investigation/metrics/edge_batch_validation.json').write_text(json.dumps({'status':'passed','official_num_layers':1,'evidence':'The one-layer edge output uses pre-attention node features; updated aggregated nodes are not fed into another block. Batching is already an exposed official predictor option. This equivalence must not be assumed for multi-layer models.','production_edge_batch_size':400000,'comparisons':rows},indent=2))
