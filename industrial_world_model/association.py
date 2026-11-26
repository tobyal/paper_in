import numpy as np
from PIL import Image
from plyfile import PlyData,PlyElement
from .common import *

def associate(ctx):
 observations=ctx.segmentation();stats=[]
 from .render import Renderer
 renderer=Renderer(ctx)
 for o in ctx.objects:
  oid=o['object_id'];ids=ctx.ids(oid);n=len(ids);observed=np.zeros(n,np.uint16);positive=np.zeros(n,np.uint16);negative=np.zeros(n,np.uint16);numerator=np.zeros(n,np.float64);denominator=np.zeros(n,np.float64);folder=ctx.path('M2.3',oid);folder.mkdir(exist_ok=True);used=[];weight_scale=max([r['view_quality'] for r in observations[oid] if r['accepted']]+[1e-9])
  for r in observations[oid]:
   if not r['accepted']:continue
   im=ctx.image_map[r['image_id']];local,pixels,visibility_weight=ctx.visibility(ids,im);mask=np.array(Image.open(ctx.out/r['mask_path']))>127;support=mask[pixels[:,1],pixels[:,0]];weight=visibility_weight*r['sam_predicted_iou']*r['view_quality']/weight_scale
   observed[local]+=1;positive[local]+=support.astype(np.uint16);negative[local]+=(~support).astype(np.uint16);numerator[local]+=weight*support;denominator[local]+=weight
   np.savez_compressed(folder/(r['image_id']+'_votes.npz'),gaussian_ids=ids[local],local_indices=local,pixels_xy=pixels,support=support.astype(np.int8),weight=weight,observation_state=np.where(support,1,-1).astype(np.int8));used.append(r['image_id'])
  scores=np.full(n,np.nan,np.float32);known=denominator>0;scores[known]=(numerator[known]/denominator[known]).astype(np.float32);np.savez_compressed(folder/'scores.npz',gaussian_ids=ids,score=scores,effective_observations=observed,positive_observations=positive,negative_observations=negative,positive_weight=numerator,total_weight=denominator);np.save(folder/'unknown_gaussian_ids.npy',ids[~known]);counts=np.histogram(scores[known],bins=np.linspace(0,1,11))[0]
  row=dict(object_id=oid,candidate_count=n,observed=int(known.sum()),unknown=int((~known).sum()),view_ids=used,score_histogram_edges=np.linspace(0,1,11).tolist(),score_histogram_counts=counts.tolist(),positive_negative_unknown_definition='Visible inside mask / visible outside mask / occluded or out of frame; only visible observations enter denominator');write(folder/'statistics.json',row);stats.append(row)
  if n:
   # A true splatted score-color view of the entire candidate subset, including unknown gray.
   import torch
   from m0.native_3dgs import subset_model
   model=subset_model(renderer.model,ids);colors=np.full((n,3),.45,np.float32);colors[known]=np.stack([1-scores[known],scores[known],np.full(known.sum(),.1)],1);view=renderer.virtual(o['bbox']['center'],o['bbox']['size']);raw=renderer.pass_colors(view,torch.as_tensor(colors,device='cuda'),model=model).permute(1,2,0).detach().cpu().numpy();save_image(folder/'score_render.png',raw)
  print('M2.3 association',o['name_en'],int(known.sum()),'known /',n,flush=True)
 write(ctx.path('M2.3','statistics.json'),stats);sheet([ctx.path('M2.3',o['object_id'],'score_render.png') for o in ctx.objects if o['candidate_count']],ctx.path('M2.3','score_overview.jpg'),labels=[o['name_en'] for o in ctx.objects if o['candidate_count']])
 return dict(objects=len(stats),candidate_observations=sum(s['candidate_count'] for s in stats),unknown_total=sum(s['unknown'] for s in stats),score_arrays_saved_before_thresholding=True)

def extract(ctx):
 cfg=ctx.c['association'];N=len(ctx.xyz);objects=ctx.objects;claims={};initial={};arrays={};winner=np.full(N,-1,np.int16);conflict_ids=[];conflict_rows=[]
 for k,o in enumerate(objects):
  oid=o['object_id']
  # Materialize NPZ members once. Indexing NpzFile inside the per-Gaussian loop
  # repeatedly decompresses the whole member and makes extraction quadratic.
  with np.load(ctx.path('M2.3',oid,'scores.npz')) as archive:a={name:archive[name] for name in archive.files}
  arrays[oid]=a;keep=(a['score']>=cfg['score_threshold'])&(a['effective_observations']>=cfg['minimum_observations'])&(a['positive_observations']>=cfg['minimum_positive_observations']);local=np.flatnonzero(keep);initial[oid]=local;folder=ctx.path('M2.4',oid);folder.mkdir(exist_ok=True);np.save(folder/'initial_selected_ids.npy',a['gaussian_ids'][local]);np.save(folder/'before_local_denoising_ids.npy',a['gaussian_ids'][local]);np.save(folder/'after_local_denoising_ids.npy',a['gaussian_ids'][local])
  for j in local:
   gid=int(a['gaussian_ids'][j]);reliability=float(a['score'][j]*(1-np.exp(-float(a['effective_observations'][j])/3)));claims.setdefault(gid,[]).append((k,int(j),reliability,float(a['score'][j]),int(a['effective_observations'][j])))
 for gid,values in claims.items():
  ranked=sorted(values,key=lambda r:r[2],reverse=True)
  if len(ranked)==1:winner[gid]=ranked[0][0]
  else:
   margin=ranked[0][2]-ranked[1][2];assigned=ranked[0][0] if margin>=cfg['conflict_margin'] else -1;winner[gid]=assigned;conflict_ids.append(gid);conflict_rows.append(dict(gaussian_id=gid,claims=[dict(object_id=objects[k]['object_id'],local_index=j,effective_support=reliability,score=score,observations=count) for k,j,reliability,score,count in ranked],margin=margin,assigned_object_id=objects[assigned]['object_id'] if assigned>=0 else None,reason='Clear effective-support margin' if assigned>=0 else 'Ambiguous overlap; no forced assignment'))
 np.save(ctx.path('M2.4','ambiguous_gaussian_ids.npy'),np.array([r['gaussian_id'] for r in conflict_rows if r['assigned_object_id'] is None],np.int64));write(ctx.path('M2.4','overlap_conflicts.json'),conflict_rows)
 ply=PlyData.read(ctx.source('ply'))['vertex'].data;instances=[]
 for k,o in enumerate(objects):
  oid=o['object_id'];ids=np.flatnonzero(winner==k);a=arrays[oid];folder=ctx.path('M2.4',oid);valid=len(ids)>=cfg['minimum_instance_gaussians'];np.save(folder/'gaussian_ids.npy',ids);uncertain=np.setdiff1d(a['gaussian_ids'],ids);np.save(folder/'not_assigned_candidate_ids.npy',uncertain);PlyData([PlyElement.describe(ply[ids].copy(),'vertex')],text=False).write(str(folder/'instance.ply'))
  row={key:o.get(key) for key in ['object_id','name_zh','name_en','description_zh','description_en','category','category_zh']};row.update(valid=valid,status='available' if valid else 'unavailable',failure_reason=None if valid else 'Too few consistently supported Gaussians; no candidate-box fallback',gaussian_count=len(ids),candidate_count=o['candidate_count'],gaussian_indices=str((folder/'gaussian_ids.npy').relative_to(ctx.out)),ply=str((folder/'instance.ply').relative_to(ctx.out)),denoising=dict(enabled=False,reason='First version preserves potentially disconnected equipment parts; before/after arrays are identical'))
  if len(ids):
   points=ctx.industrial[ids];lo=points.min(0);hi=points.max(0);local=np.searchsorted(a['gaussian_ids'],ids);row.update(center=((lo+hi)/2).tolist(),centroid=points.mean(0).tolist(),bbox=dict(center=((lo+hi)/2).tolist(),size=(hi-lo).tolist(),minimum=lo.tolist(),maximum=hi.tolist(),quaternion=[0,0,0,1]),confidence=dict(mean_support_score=float(a['score'][local].mean()),median_effective_observations=float(np.median(a['effective_observations'][local])),not_probability=True))
  else:row.update(center=None,centroid=None,bbox=None,confidence=None)
  write(folder/'instance.json',row);instances.append(row);print('M2.4 instance',o['name_en'],len(ids),'/',o['candidate_count'],row['status'],flush=True)
 write(ctx.path('M2.4','instances.json'),instances)
 return dict(objects=len(instances),available=sum(i['valid'] for i in instances),unavailable=[i['object_id'] for i in instances if not i['valid']],final_gaussians=sum(i['gaussian_count'] for i in instances),overlap_conflicts=len(conflict_rows),unresolved_conflicts=sum(r['assigned_object_id'] is None for r in conflict_rows),local_denoising=False)
