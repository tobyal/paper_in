import re,importlib.metadata
import numpy as np,torch
from PIL import Image
from .common import *

def load_clip(ctx):
 import open_clip
 model,_,preprocess=open_clip.create_model_and_transforms(ctx.c['input']['clip_arch'],pretrained=str(ctx.source('clip')),device='cuda');model.eval().requires_grad_(False)
 return model,preprocess,open_clip.get_tokenizer(ctx.c['input']['clip_arch'])
def heatmap(matrix,path,labels,title):
 import matplotlib.pyplot as plt
 n=len(labels);fig,ax=plt.subplots(figsize=(max(5,n*.29),max(4,n*.29)));im=ax.imshow(matrix,vmin=-.1,vmax=1,cmap='viridis');ax.set_xticks(range(n));ax.set_yticks(range(n));ax.set_xticklabels(labels,rotation=90,fontsize=5);ax.set_yticklabels(labels,fontsize=5);ax.set_title(title);fig.colorbar(im,ax=ax);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)
def visual(ctx):
 model,preprocess,_=load_clip(ctx);observations=ctx.segmentation();records={};cfg=ctx.c['semantics'];count=0
 with torch.inference_mode():
  for o in ctx.objects:
   oid=o['object_id'];folder=ctx.path('M3.1',oid);folder.mkdir(exist_ok=True);features=[];rows=[];paths=[]
   for r in observations[oid]:
    if not r['accepted']:continue
    im=ctx.image_map[r['image_id']];rgb=ctx.rgb(im);mask=np.array(Image.open(ctx.out/r['mask_path']))>127;y,x=np.where(mask)
    if not len(x):continue
    pad=int(max(np.ptp(x),np.ptp(y))*cfg['crop_padding_fraction'])+1;x0,x1=max(0,int(x.min())-pad),min(im['width'],int(x.max())+pad+1);y0,y1=max(0,int(y.min())-pad),min(im['height'],int(y.max())+pad+1);raw=rgb[y0:y1,x0:x1];masked=raw.copy();masked[~mask[y0:y1,x0:x1]]=cfg['masked_background'];stem=folder/r['image_id'];save_image(stem.with_name(stem.name+'_crop.png'),raw);save_image(stem.with_name(stem.name+'_masked.png'),masked)
    feature=model.encode_image(preprocess(Image.fromarray(masked)).unsqueeze(0).cuda()).float();feature=torch.nn.functional.normalize(feature,dim=-1)[0].cpu().numpy();np.save(stem.with_suffix('.npy'),feature);features.append(feature);rows.append(dict(image_id=r['image_id'],crop_xyxy=[x0,y0,x1,y1],mask_path=r['mask_path'],source_image=r['source_rgb'],masked_background=cfg['masked_background'],view_quality=r['view_quality'],sam_predicted_iou=r['sam_predicted_iou'],feature_path=str(stem.with_suffix('.npy').relative_to(ctx.out)),masked_crop=str(stem.with_name(stem.name+'_masked.png').relative_to(ctx.out))));paths.append(stem.with_name(stem.name+'_masked.png'));count+=1
   array=np.stack(features) if features else np.empty((0,512),np.float32);np.save(folder/'features.npy',array);write(folder/'views.json',rows);sheet(paths,folder/'multiview_crops.jpg',labels=[r['image_id'] for r in rows]);records[oid]=rows;print('M3.1 encode',o['name_en'],len(rows),flush=True)
 write(ctx.path('M3.1','observations.json'),records);write(ctx.path('M3.1','model.json'),dict(architecture=ctx.c['input']['clip_arch'],checkpoint=str(ctx.source('clip').relative_to(ctx.project)),checkpoint_sha256=sha(ctx.source('clip')),open_clip_version=importlib.metadata.version('open_clip_torch'),feature_dimension=512,input_resolution=224,preprocessing=str(preprocess),mask_background=cfg['masked_background'],crop_padding_fraction=cfg['crop_padding_fraction'],historical_features_reused=False))
 return dict(objects=len(records),visual_observations=count,feature_dimension=512)
def aggregate(ctx):
 objects=ctx.objects;cfg=ctx.c['semantics'];records=[];embeddings=[]
 for o in objects:
  oid=o['object_id'];features=np.load(ctx.path('M3.1',oid,'features.npy'));views=read(ctx.path('M3.1',oid,'views.json'));n=len(features);dest=ctx.path('M3.2',oid);dest.mkdir(exist_ok=True);similarity=features@features.T;keep=np.ones(n,bool);mean=np.zeros(n);reason='Too few observations for distribution-based filtering; normalized quality-weighted average'
  if n>1:mean=(similarity.sum(1)-1)/(n-1)
  median=float(np.median(mean)) if n else None;mad=float(np.median(abs(mean-median))) if n else None;threshold=None
  if n>=cfg['outlier_minimum_views'] and mad>=cfg['outlier_minimum_mad']:
   threshold=median-cfg['outlier_mad_multiplier']*1.4826*mad;keep=mean>=threshold;reason='Median/MAD filtering of cross-view mean cosine similarity'
  elif n>=cfg['outlier_minimum_views']:reason='Cross-view similarity spread too small for useful outlier threshold; all retained'
  weights=np.array([r['view_quality']*r['sam_predicted_iou'] for r in views])*keep
  weights=weights/max(weights.sum(),1e-12);feature=normalize((features*weights[:,None]).sum(0)[None])[0] if n else np.zeros(512,np.float32);embeddings.append(feature);np.save(dest/'cosine_similarity.npy',similarity);np.save(dest/'weights.npy',weights);np.save(dest/'visual_feature.npy',feature)
  row=dict(object_id=oid,available=n>0,views=n,kept=int(keep.sum()),mean_cosine_similarity=mean.tolist(),median=median,mad=mad,threshold=threshold,weights=weights.tolist(),kept_mask=keep.tolist(),excluded=[dict(image_id=views[i]['image_id'],reason='Cross-view cosine below robust threshold') for i in range(n) if not keep[i]],policy=reason,view_ids=[v['image_id'] for v in views]);write(dest/'aggregation.json',row);records.append(row)
  if n:heatmap(similarity,dest/'view_similarity.png',[v['image_id'][-3:] for v in views],'Cross-view cosine similarity')
 np.save(ctx.path('M3.2','visual_features.npy'),np.array(embeddings,np.float32));write(ctx.path('M3.2','aggregation.json'),records)
 return dict(objects=len(objects),visual_available=sum(r['available'] for r in records),observations=sum(r['views'] for r in records),excluded_observations=sum(r['views']-r['kept'] for r in records),official_rofa_exact_reproduction=False,rofa_inspired='Quality-weighted normalized pooling, meaningful-sample-size guarded robust consistency filtering')
def text(ctx):
 model,_,tokenizer=load_clip(ctx);prompts=[];records=[]
 for o in ctx.objects:
  # Remove annotation-workflow suffix only in the encoder input; preserve all M0 strings.
  name=re.sub(r'\s+\d+$','',o['name_en']).strip();description=o.get('description_en','');description=re.split(r'Initial Codex box|pending human review',description,flags=re.I)[0].strip();prompt=f'A photo of {name}. '+description
  prompts.append(prompt.strip());records.append(dict(object_id=o['object_id'],original_name_en=o['name_en'],original_description_en=o.get('description_en',''),encoded_text=prompt.strip(),description_missing=not bool(o.get('description_en')),fallback='Existing English name only' if not o.get('description_en') else None,m0_text_modified=False))
 with torch.inference_mode():features=torch.nn.functional.normalize(model.encode_text(tokenizer(prompts).cuda()).float(),dim=-1).cpu().numpy()
 np.save(ctx.path('M3.3','text_features.npy'),features);write(ctx.path('M3.3','text_inputs.json'),records)
 return dict(objects=len(records),feature_dimension=features.shape[1],name_only_objects=sum(r['description_missing'] for r in records),encoder_compatible_with_visual=True,m0_unchanged=True)
def combine(ctx):
 objects=ctx.objects;instances=ctx.instances();visual=np.load(ctx.path('M3.2','visual_features.npy'));text_features=np.load(ctx.path('M3.3','text_features.npy'));aggregation=read(ctx.path('M3.2','aggregation.json'));records=[]
 for k,(o,instance) in enumerate(zip(objects,instances)):
  assert o['object_id']==instance['object_id'];records.append({**instance,'feature_row':k,'visual_available':bool(np.linalg.norm(visual[k])>.5),'text_available':bool(np.linalg.norm(text_features[k])>.5),'aggregation':aggregation[k],'semantic_available':bool(instance['valid'] and np.linalg.norm(visual[k])>.5)})
 np.savez_compressed(ctx.path('M3.4','features.npz'),visual=visual,text=text_features);write(ctx.path('M3.4','objects.json'),records);sim=visual@visual.T;textsim=text_features@text_features.T;np.save(ctx.path('M3.4','visual_cosine.npy'),sim);np.save(ctx.path('M3.4','text_cosine.npy'),textsim);names=[o['category']+' '+o['name_en'].split()[-1] for o in objects];heatmap(sim,ctx.path('M3.4','object_visual_similarity.png'),names,'Object visual cosine (not probability)');heatmap(textsim,ctx.path('M3.4','object_text_similarity.png'),names,'Object text cosine (not probability)')
 within=[];between=[]
 for i in range(len(objects)):
  for j in range(i):
   if records[i]['semantic_available'] and records[j]['semantic_available']:(within if objects[i]['category']==objects[j]['category'] else between).append(float(sim[i,j]))
 diagnostics=dict(within_category_mean_cosine=float(np.mean(within)) if within else None,between_category_mean_cosine=float(np.mean(between)) if between else None,within_pairs=len(within),between_pairs=len(between),not_classification_accuracy=True);write(ctx.path('M3.4','semantic_diagnostics.json'),diagnostics)
 return dict(objects=len(records),multimodal_available=sum(r['semantic_available'] for r in records),separate_visual_text_branches=True,**diagnostics)
