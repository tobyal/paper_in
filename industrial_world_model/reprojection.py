import numpy as np
from PIL import Image
from plyfile import PlyData,PlyElement
from .common import *

def run(ctx):
 from .render import Renderer
 renderer=Renderer(ctx);observations=ctx.segmentation();objects={o['object_id']:o for o in ctx.objects};rows=[];gallery=[]
 for instance in ctx.instances():
  oid=instance['object_id'];folder=ctx.path('M2.5',oid);folder.mkdir(exist_ok=True)
  if not instance['valid']:write(folder/'unavailable.json',dict(reason=instance['failure_reason']));continue
  ids=ctx.ids(oid,True);candidates=ctx.ids(oid);paths=[];per_object=[]
  for r in observations[oid]:
   if not r['accepted']:continue
   im=ctx.image_map[r['image_id']];dest=folder/r['image_id'];dest.mkdir(exist_ok=True);mass=renderer.contribution(im,ids);alpha=np.load(ctx.path('M2.1','full_scene_depth',r['image_id']+'.npz'))['alpha'];fraction=mass/np.maximum(alpha,1e-8);projected=(fraction>=ctx.c['reprojection']['minimum_instance_contribution'])&(alpha>=ctx.c['visibility']['minimum_alpha']);sam=np.array(Image.open(ctx.out/r['mask_path']))>127
   intersection=int((sam&projected).sum());union=int((sam|projected).sum());prediction=int(projected.sum());truth=int(sam.sum());row=dict(object_id=oid,image_id=r['image_id'],iou=intersection/max(union,1),sam_coverage=intersection/max(truth,1),projection_excess=int((projected&~sam).sum())/max(prediction,1),sam_pixels=truth,projection_pixels=prediction,diagnostic_only=True,independent_ground_truth=False,full_scene_occlusion=True);rows.append(row);per_object.append(row)
   np.savez_compressed(dest/'contribution.npz',instance_alpha=mass.astype(np.float32),full_scene_alpha=alpha,normalized_instance_contribution=fraction.astype(np.float32));mask_image(dest/'projected_mask.png',projected);rgb=ctx.rgb(im);difference=np.zeros_like(rgb);difference[sam&projected]=[45,195,100];difference[sam&~projected]=[50,120,255];difference[projected&~sam]=[255,85,60];save_image(dest/'difference.png',difference);save_image(dest/'sam_overlay.jpg',overlay(rgb,sam,(40,205,110)));save_image(dest/'projection_overlay.jpg',overlay(rgb,projected,(255,140,50)));save_image(dest/'original.jpg',rgb);sheet([dest/'original.jpg',dest/'sam_overlay.jpg',dest/'projection_overlay.jpg',dest/'difference.png'],dest/'comparison.jpg',labels=['Original RGB','SAM input (not truth)','3D instance, full occlusion','Green intersection / blue missed / red excess'],columns=4,tile=(480,310));save_image(dest/'instance_independent.jpg',renderer.rgb(im,ids,width=960));save_image(dest/'instance_highlight.jpg',renderer.highlight(im,[(ids,[1,.28,.06])],width=960));write(dest/'metrics.json',row);paths.append(dest/'comparison.jpg')
  write(folder/'consistency.json',per_object);sheet(paths,folder/'multiview_consistency.jpg',columns=2,tile=(800,250));
  if paths:gallery.append(paths[0])
  virtual=[]
  for axis in ['oblique','side','top']:
   im=renderer.virtual(instance['center'],instance['bbox']['size'],axis);write(folder/('camera_'+axis+'.json'),im);save_image(folder/('candidate_'+axis+'.jpg'),renderer.rgb(im,candidates));save_image(folder/('instance_'+axis+'.jpg'),renderer.rgb(im,ids));virtual.extend([folder/('candidate_'+axis+'.jpg'),folder/('instance_'+axis+'.jpg')])
  sheet(virtual,folder/'candidate_vs_instance.jpg',labels=['Candidate oblique','Final oblique','Candidate side','Final side','Candidate top','Final top'],columns=2,tile=(400,425));print('M2.5 reprojection',instance['name_en'],len(per_object),'views',flush=True)
 write(ctx.path('M2.5','consistency.json'),rows);sheet(gallery,ctx.path('M2.5','reprojection_overview.jpg'),columns=2,tile=(800,250))
 return dict(available_objects=len(set(r['object_id'] for r in rows)),observations=len(rows),mean_internal_iou=float(np.mean([r['iou'] for r in rows])) if rows else None,mean_sam_coverage=float(np.mean([r['sam_coverage'] for r in rows])) if rows else None,not_segmentation_accuracy=True,all_visibility_uses_complete_source_scene=True)

def semantic_map(ctx):
 from .render import Renderer
 renderer=Renderer(ctx);instances=ctx.instances();labels=np.zeros(len(ctx.xyz),np.int16);lookup=[];groups=[]
 for o in ctx.objects:labels[ctx.ids(o['object_id'])]=-1
 for k,row in enumerate(instances,1):
  ids=ctx.ids(row['object_id'],True)
  if row['valid']:labels[ids]=k;groups.append((ids,object_color(k)))
  lookup.append(dict(label=k,object_id=row['object_id'],name_zh=row['name_zh'],name_en=row['name_en'],category=row['category'],valid=row['valid'],color_rgb=(object_color(k)*255).astype(int).tolist(),gaussian_ids=str(ctx.path('M2.4',row['object_id'],'gaussian_ids.npy').relative_to(ctx.out))))
 np.save(ctx.path('M2.6','gaussian_to_object.npy'),labels);write(ctx.path('M2.6','label_lookup.json'),dict(background=0,unassigned_candidate=-1,objects=lookup));write(ctx.path('M2.6','objects.json'),instances)
 ply=PlyData.read(ctx.source('ply'))['vertex'].data.copy()
 for k,row in enumerate(instances,1):
  if not row['valid']:continue
  ids=ctx.ids(row['object_id'],True);color=object_color(k)
  for i in range(3):ply['f_dc_'+str(i)][ids]=(color[i]-.5)/.28209479177387814
  for name in ply.dtype.names:
   if name.startswith('f_rest_'):ply[name][ids]=0
 PlyData([PlyElement.describe(ply,'vertex')],text=False).write(str(ctx.path('M2.6','semantic_native_3dgs.ply')))
 paths=[]
 for im in read(ctx.out/'config/reference_cameras.json'):
  path=ctx.path('M2.6',im['image_id']+'_semantic_map.jpg');save_image(path,renderer.highlight(im,groups,width=1200));paths.append(path)
 sheet(paths,ctx.path('M2.6','semantic_map_overview.jpg'),columns=2,tile=(600,365))
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(figsize=(10,12));ax.set_aspect('equal')
 for k,row in enumerate(instances,1):
  if not row['valid']:continue
  pts=ctx.industrial[ctx.ids(row['object_id'],True)];step=max(1,len(pts)//3500);ax.scatter(pts[::step,0],pts[::step,1],c=[object_color(k)],s=1);ax.text(row['center'][0],row['center'][1],row['name_en'],fontsize=5)
 ax.set(xlabel='Industrial X (SfM units)',ylabel='Industrial Y (SfM units)',title='33 prior-defined instances: extracted Gaussian centers');fig.tight_layout();fig.savefig(ctx.path('M2.6','semantic_map_top.png'),dpi=180);plt.close(fig)
 return dict(objects=len(instances),available=sum(r['valid'] for r in instances),labeled_gaussians=int((labels>0).sum()),unassigned_candidate_gaussians=int((labels<0).sum()),background_gaussians=int((labels==0).sum()),full_scene_background_appearance_preserved=True)
