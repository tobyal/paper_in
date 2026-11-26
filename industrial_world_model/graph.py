import numpy as np
from .common import *

INVERSE={'left_of':'right_of','right_of':'left_of','in_front_of':'behind','behind':'in_front_of','above':'below','below':'above','near':'near','same_category':'same_category'}
def pair_relations(a,b,cfg):
 lo1=np.array(a['bbox']['minimum']);hi1=np.array(a['bbox']['maximum']);lo2=np.array(b['bbox']['minimum']);hi2=np.array(b['bbox']['maximum']);gaps=np.maximum(np.maximum(lo2-hi1,lo1-hi2),0);distance=float(np.linalg.norm(gaps));delta=np.array(a['center'])-b['center'];overlap=np.maximum(np.minimum(hi1,hi2)-np.maximum(lo1,lo2),0);tol=cfg['axis_separation'];relations=[]
 # Extent separation is deliberately stricter than ordering nearly coincident centers.
 for axis,negative,positive in [(0,'left_of','right_of'),(1,'behind','in_front_of'),(2,'below','above')]:
  if lo2[axis]-hi1[axis]>=tol:relations.append((negative,float(lo2[axis]-hi1[axis]),axis))
  elif lo1[axis]-hi2[axis]>=tol:relations.append((positive,float(lo1[axis]-hi2[axis]),axis))
 if distance<=cfg['near_distance']:relations.append(('near',distance,None))
 if a['category']==b['category']:relations.append(('same_category',None,None))
 basis=dict(subject_minus_object_center=delta.tolist(),aabb_axis_gaps=gaps.tolist(),aabb_minimum_distance=distance,aabb_overlap_volume=float(np.prod(overlap)),coordinate_frame='industrial',units='sfm_relative')
 return relations,basis
def run(ctx):
 semantics=read(ctx.path('M3.4','objects.json'));cfg=ctx.c['relations'];N=len(semantics);distances=np.full((N,N),np.nan);deltas=np.full((N,N,3),np.nan);nodes=[];edges=[];pairs=[]
 for o in semantics:
  nodes.append({**o,'visual_feature':{'path':'../M3_semantic_fusion/M3_4_object_semantics/features.npz','key':'visual','row':o['feature_row']},'text_feature':{'path':'../M3_semantic_fusion/M3_4_object_semantics/features.npz','key':'text','row':o['feature_row']},'geometry_basis':'M2 final Gaussian centers, never M0 coarse boxes','size':o['bbox']['size'] if o['bbox'] else None,'available':o['semantic_available']})
 for i,a in enumerate(nodes):
  if not a['available']:continue
  distances[i,i]=0;deltas[i,i]=0
  for j,b in enumerate(nodes):
   if i==j or not b['available']:continue
   relations,basis=pair_relations(a,b,cfg);distances[i,j]=basis['aabb_minimum_distance'];deltas[i,j]=basis['subject_minus_object_center'];pairs.append(dict(subject_id=a['object_id'],object_id=b['object_id'],**basis))
   for relation,value,axis in relations:edges.append(dict(subject_id=a['object_id'],relation=relation,object_id=b['object_id'],evidence={**basis,'axis':axis,'value':value,'threshold':cfg['near_distance'] if relation=='near' else cfg['axis_separation'] if axis is not None else None,'same_category':a['category'] if relation=='same_category' else None},certainty='deterministic_under_estimated_instance_geometry',geometry_confidence=[a['confidence'],b['confidence']]))
 keys={(r['subject_id'],r['relation'],r['object_id']) for r in edges};assert len(keys)==len(edges)
 for a,r,b in keys:assert (b,INVERSE[r],a) in keys
 np.save(ctx.path('M4','distance_matrix.npy'),distances);np.save(ctx.path('M4','relative_position_matrix.npy'),deltas);write(ctx.path('M4','matrix_object_ids.json'),[n['object_id'] for n in nodes]);write(ctx.path('M4','nodes.json'),nodes);write(ctx.path('M4','pair_geometry.json'),pairs);write(ctx.path('M4','relations.json'),edges);write(ctx.path('M4','scene_graph.json'),dict(nodes=nodes,edges=edges,coordinate_system=ctx.state['scene']['transform'],direction_convention=cfg['directions'],thresholds=cfg,units='sfm_relative',unavailable_nodes=[n['object_id'] for n in nodes if not n['available']]))
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(figsize=(12,12));ax.set_aspect('equal');lookup={n['object_id']:n for n in nodes}
 for edge in edges:
  if edge['relation']=='near' and edge['subject_id']<edge['object_id']:
   a,b=lookup[edge['subject_id']],lookup[edge['object_id']];ax.plot([a['center'][0],b['center'][0]],[a['center'][1],b['center'][1]],color='#aaa',alpha=.5,lw=.8)
 for k,n in enumerate(nodes,1):
  if n['available']:ax.scatter(*n['center'][:2],c=[object_color(k)],s=70);ax.text(n['center'][0]+.04,n['center'][1],n['category']+' '+n['name_en'].split()[-1],fontsize=6)
 ax.set(xlabel='Industrial X (SfM units)',ylabel='Industrial Y: forward (+Y)',title='Instance scene graph: near edges (complete relation set in JSON)');fig.tight_layout();fig.savefig(ctx.path('M4','scene_graph_near.png'),dpi=180);plt.close(fig)
 fig=plt.figure(figsize=(12,8));ax=fig.add_subplot(111,projection='3d')
 for k,n in enumerate(nodes,1):
  if n['available']:ax.scatter(*n['center'],c=[object_color(k)],s=35);ax.text(*n['center'],str(k),fontsize=7)
 for edge in edges:
  if edge['relation']=='near' and edge['subject_id']<edge['object_id']:
   a,b=lookup[edge['subject_id']]['center'],lookup[edge['object_id']]['center'];ax.plot([a[0],b[0]],[a[1],b[1]],[a[2],b[2]],alpha=.35,color='gray')
 ax.set(xlabel='X',ylabel='Y',zlabel='Z',title='Extracted instance centers and near relations');fig.tight_layout();fig.savefig(ctx.path('M4','relations_3d.png'),dpi=160);plt.close(fig)
 counts={rel:sum(e['relation']==rel for e in edges) for rel in INVERSE};write(ctx.path('M4','relation_validation.json'),dict(inverse_and_symmetric_checks_passed=True,edge_keys_unique=True,relation_counts=counts))
 return dict(nodes=N,available_nodes=sum(n['available'] for n in nodes),directed_edges=len(edges),relation_counts=counts,inverse_and_symmetric_consistency=True)
