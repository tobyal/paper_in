import collections,shutil,traceback,time
import numpy as np,torch
from PIL import Image,ImageDraw
from .common import *

def run(ctx):
 from segment_anything import sam_model_registry,SamPredictor
 model=sam_model_registry['vit_h'](checkpoint=str(ctx.source('sam'))).cuda().eval();model.requires_grad_(False);predictor=SamPredictor(model);selected=ctx.selected();tasks=collections.defaultdict(list);objects={o['object_id']:o for o in ctx.objects};cfg=ctx.c['sam']
 for oid,views in selected.items():
  for view in views:tasks[view['image_id']].append((oid,view))
 observations={oid:[] for oid in selected};paths=[];encodings=0;inference=0;checkpoint_hash=sha(ctx.source('sam'))
 with torch.inference_mode():
  for j,(iid,pairs) in enumerate(sorted(tasks.items())):
   im=ctx.image_map[iid];rgb=ctx.rgb(im);source=ctx.path('M2.2','images',im['filename']);source.parent.mkdir(exist_ok=True)
   if not source.exists():shutil.copy2(ctx.source('images')/im['filename'],source)
   cache=ctx.path('M2.2','image_embeddings',iid);cache.parent.mkdir(exist_ok=True)
   compatible=cache.with_suffix('.npy').exists() and cache.with_suffix('.json').exists() and read(cache.with_suffix('.json')).get('checkpoint_sha256')==checkpoint_hash
   if compatible:
    meta=read(cache.with_suffix('.json'));assert meta['image_sha256']==im['sha256'];predictor.features=torch.from_numpy(np.load(cache.with_suffix('.npy'))).cuda();predictor.original_size=tuple(meta['original_size']);predictor.input_size=tuple(meta['input_size']);predictor.is_image_set=True
   else:
    predictor.set_image(rgb);np.save(cache.with_suffix('.npy'),predictor.features.cpu().numpy());write(cache.with_suffix('.json'),dict(image_sha256=im['sha256'],checkpoint_sha256=checkpoint_hash,original_size=predictor.original_size,input_size=predictor.input_size,model='SAM ViT-H',source='fresh current-run original RGB encoding'));encodings+=1
   for oid,view in pairs:
    folder=ctx.path('M2.2',oid,iid);folder.mkdir(parents=True,exist_ok=True);start=time.time();record=dict(object_id=oid,image_id=iid,prompt=dict(bbox=view['bbox'],points=[],labels=[]),image_sha256=im['sha256'],width=im['width'],height=im['height'],view_quality=view['score'],visible_fraction=view['visible_fraction'],source_rgb=str(source.relative_to(ctx.out)),accepted=False)
    try:
     masks,scores,logits=predictor.predict(box=np.array(view['bbox'],np.float32),multimask_output=True);inference+=1;assert masks.shape[1:]==rgb.shape[:2];np.savez_compressed(folder/'sam_logits.npz',logits=logits);local,pixels,weights=ctx.visibility(ctx.ids(oid),im);np.savez_compressed(folder/'visible_candidate_centers.npz',local_indices=local,pixels_xy=pixels,weights=weights)
     x0,y0,x1,y1=np.array(view['bbox']).astype(int);boxarea=max(1,(x1-x0+1)*(y1-y0+1));candidates=[]
     for k,mask in enumerate(masks):
      mask_image(folder/f'candidate_{k}.png',mask);inside_pixels=int(mask[max(y0,0):y1+1,max(x0,0):x1+1].sum());count=int(mask.sum());outside=1-inside_pixels/max(count,1);recall=float(np.average(mask[pixels[:,1],pixels[:,0]],weights=weights)) if len(pixels) else 0.;occupancy=count/boxarea;reasons=[]
      if count<cfg['minimum_pixels']:reasons.append('too few pixels')
      if float(scores[k])<cfg['minimum_predicted_iou']:reasons.append('low SAM predicted IoU')
      if recall<cfg['minimum_visible_center_recall']:reasons.append('insufficient visible candidate-center support')
      if outside>cfg['maximum_outside_box_fraction']:reasons.append('excessive leakage outside prompt')
      if occupancy<cfg['minimum_box_occupancy']:reasons.append('tiny fragment relative to prompt')
      candidates.append(dict(index=k,sam_predicted_iou=float(scores[k]),pixels=count,visible_center_recall=recall,outside_box_fraction=outside,box_occupancy=occupancy,selection_score=.5*float(scores[k])+.4*recall+.1*(1-outside),rejected_reasons=reasons))
     reliable=[r for r in candidates if not r['rejected_reasons']];choice=max(reliable or candidates,key=lambda r:r['selection_score']);mask=masks[choice['index']];record.update(candidates=candidates,selected_candidate=choice['index'],accepted=bool(reliable),sam_predicted_iou=choice['sam_predicted_iou'],selection_reason='Highest uniform confidence + visible-center support + in-box score among accepted candidates; rejected best candidate retained for diagnosis if none accepted',failure_reason=None if reliable else 'No SAM candidate passes uniform reliability gates')
     mask_image(folder/'selected_mask.png',mask);picture=Image.fromarray(overlay(rgb,mask,color=(50,210,130) if reliable else (245,75,60)));draw=ImageDraw.Draw(picture);draw.rectangle(view['bbox'],outline='#ffc75c',width=3);picture.thumbnail((960,600));save_image(folder/'overlay.jpg',picture)
     crop=rgb[max(y0,0):y1+1,max(x0,0):x1+1].copy();cropped_mask=mask[max(y0,0):y1+1,max(x0,0):x1+1];crop[~cropped_mask]=127;save_image(folder/'masked_prompt_crop.png',crop);record['mask_path']=str((folder/'selected_mask.png').relative_to(ctx.out));paths.append(folder/'overlay.jpg')
    except Exception as e:record.update(failure_reason=str(e),traceback=traceback.format_exc());traceback.print_exc()
    record['seconds']=time.time()-start;write(folder/'observation.json',record);observations[oid].append(record)
   write(ctx.path('M2.2','observations.json'),observations);print('M2.2 SAM image',j+1,len(tasks),iid,'prompts',len(pairs),flush=True)
 for oid,obs in observations.items():sheet([ctx.path('M2.2',oid,r['image_id'],'overlay.jpg') for r in obs if (ctx.path('M2.2',oid,r['image_id'],'overlay.jpg')).exists()],ctx.path('M2.2',oid,'multiview_segmentation.jpg'),labels=[r['image_id']+(' accepted' if r['accepted'] else ' rejected') for r in obs])
 sheet(paths[::max(1,len(paths)//40)],ctx.path('M2.2','segmentation_overview.jpg'))
 return dict(objects=len(observations),observations=sum(map(len,observations.values())),accepted=sum(r['accepted'] for v in observations.values() for r in v),fresh_image_encodings=encodings,prompt_inferences=inference,box_prompt_only=True,mask_pixels='Exact original RGB width/height',reused_prior_masks=False)
