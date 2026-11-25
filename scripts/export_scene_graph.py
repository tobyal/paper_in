#!/usr/bin/env python3
"""Serialize predicted scene graph and show geometry without altering predictions."""
import argparse,json,pathlib,collections
import numpy as np
import torch
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plyfile import PlyData,PlyElement
p=argparse.ArgumentParser();p.add_argument('--audit',required=True);p.add_argument('--output',required=True);p.add_argument('--levels',type=int,nargs='+',default=[2,3]);a=p.parse_args();source=pathlib.Path(a.audit);out=pathlib.Path(a.output)
for d in ['data','metrics','visualizations']:(out/d).mkdir(parents=True,exist_ok=True)
summary=[]
for level in a.levels:
    inputs=torch.load(source/f'level_{level}_graph_inputs.pt',map_location='cpu');pred=torch.load(source/f'level_{level}_edge_predictions.pt',map_location='cpu')
    centers=np.asarray(inputs['centers']);extents=np.asarray(inputs['extents']);rot=np.asarray(inputs['rotations']);ids=inputs['original_cluster_ids'];sims=np.asarray(pred['relation_similarities']);classes=pred['relation_names']
    top=np.argsort(sims,axis=1)[:,-3:][:,::-1]
    nodes=[{'row':i,'cluster_id':int(cid),'center_centered_frame':centers[i].tolist(),'rotation':rot[i].tolist(),'extent':extents[i].tolist()} for i,cid in enumerate(ids)]
    edges=[{'source_row':int(src),'target_row':int(dst),'source_cluster_id':int(ids[src]),'target_cluster_id':int(ids[dst]),'top3':[{'relation':classes[j],'cosine_similarity':float(sims[k,j])} for j in top[k]]} for k,(src,dst) in enumerate(zip(pred['src'],pred['dst']))]
    (out/'data'/f'level_{level}_scene_graph.json').write_text(json.dumps({'level':level,'nodes':nodes,'edges':edges,'coordinates':'Predictor centers original COLMAP points before OBB estimation; units and gravity uncalibrated','index_mapping_identity':list(map(int,ids))==list(range(len(ids)))},indent=2))
    hist=collections.Counter(e['top3'][0]['relation'] for e in edges)
    summary.append({'level':level,'nodes':len(nodes),'edges':len(edges),'top1_relation_counts':dict(hist),'index_mapping_identity':list(map(int,ids))==list(range(len(ids)))})
    verts=np.empty(len(nodes),dtype=[('x','f4'),('y','f4'),('z','f4'),('cluster_id','i4')])
    for j,n in enumerate(['x','y','z']):verts[n]=centers[:,j]
    verts['cluster_id']=ids
    ed=np.empty(len(edges),dtype=[('vertex1','i4'),('vertex2','i4')]);ed['vertex1']=pred['src'];ed['vertex2']=pred['dst']
    PlyData([PlyElement.describe(verts,'vertex'),PlyElement.describe(ed,'edge')]).write(out/'visualizations'/f'level_{level}_graph.ply')
    fig=plt.figure(figsize=(12,8));ax=fig.add_subplot(111,projection='3d');ax.scatter(*centers.T,s=12)
    # The diagram shows only the 100 highest cosine edges for readability; JSON/PLY retain every edge.
    ranked=sorted(range(len(edges)),key=lambda k:edges[k]['top3'][0]['cosine_similarity'],reverse=True)[:100]
    for k in ranked:
        e=edges[k];c=centers[[e['source_row'],e['target_row']]];ax.plot(*c.T,alpha=.25,linewidth=.6)
    ax.set(xlabel='COLMAP x',ylabel='COLMAP y',zlabel='COLMAP z',title=f'Level {level}: {len(nodes)} nodes, {len(edges)} edges; top 100 shown')
    fig.savefig(out/'visualizations'/f'level_{level}_graph.png',dpi=160);plt.close(fig)
(out/'metrics/scene_graph_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
