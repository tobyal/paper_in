"""Select complementary existing full-scene views and make fresh SAM prompts only."""
import collections,cv2,torch
from segment_anything import sam_model_registry,SamPredictor
from common import *
from industrial_world_model.hybrid_views.geometry import box_projection
from industrial_world_model.render import Renderer

cfg=read(ROOT/'configs/experiment.json');objects=read(ROOT/'inputs/objects.json')
T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])
hybrid=PROJECT/read(ROOT/'inputs/manifest.json')['hybrid_observations']
selected=read(hybrid/'selected_views.json');cammap={c['image_id']:c for c in read(hybrid/'selected_cameras.json')}
original={c['image_id']:c for c in read(ROOT/'inputs/cameras.json')}
trained={c['image_id'] for c in read(ROOT/'inputs/training_cameras.json')}
reuse={r['object_id'] for r in read(V1/'configs/final_quality_review.json')['objects'] if r['usable_for_queries']}
out=ROOT/'outputs/A/reference_prompts';out.mkdir(parents=True,exist_ok=True)
renderer=Renderer(NativeContext());tasks=collections.defaultdict(list);selections={};records=[]

def spread_points(mask,maximum=7):
    distance=cv2.distanceTransform(mask.astype(np.uint8),cv2.DIST_L2,5)
    if distance.max()<cfg['minimum_safe_point_distance']:return []
    coords=np.column_stack(np.nonzero(distance>=cfg['minimum_safe_point_distance']))
    # One safe interior point per coarse image cell, then spatially separated selection.
    y0,x0=coords.min(0);y1,x1=coords.max(0);pool=[]
    for gy in range(3):
        for gx in range(3):
            chosen=coords[(coords[:,0]>=y0+(y1-y0+1)*gy/3)&(coords[:,0]<y0+(y1-y0+1)*(gy+1)/3)&
                          (coords[:,1]>=x0+(x1-x0+1)*gx/3)&(coords[:,1]<x0+(x1-x0+1)*(gx+1)/3)]
            if len(chosen):
                y,x=max(chosen,key=lambda p:distance[tuple(p)]);pool.append((int(x),int(y),float(distance[y,x])))
    points=[]
    while pool and len(points)<maximum:
        best=max(pool,key=lambda p:p[2] if not points else min(np.linalg.norm(np.array(p[:2])-q) for q in points)*min(p[2],5))
        if points and min(np.linalg.norm(np.array(best[:2])-q) for q in points)<12:break
        points.append(best[:2]);pool.remove(best)
    return points

for obj in objects:
    oid=obj['object_id']
    if oid in reuse:
        selections[oid]=dict(mode='reuse_v1_instance_and_prompts',views=[]);continue
    candidates=candidate_ids(oid);pool=[]
    for old in selected[oid]:
        iid=old['image_id'];cam=dict(original[iid] if old['source_type']=='real' else cammap[iid])
        assert cam['split']=='train',iid
        path=PROJECT/'data/images'/cam['filename'] if old['source_type']=='real' else hybrid/old['image_path']
        c=scaled_camera(cam,cfg['reference_width']);c['source_type']=old['source_type']
        folder=out/oid/iid;folder.mkdir(parents=True,exist_ok=True)
        contribution=renderer.contribution(c,candidates).clip(0,1)
        pixels=int((contribution>.65).sum());projection=box_projection(obj['bbox'],T,c)
        np.savez_compressed(folder/'coarse_candidate_contribution.npz',contribution=contribution.astype(np.float16))
        visibility=np.load(hybrid/old['visibility_path'])['gaussian_ids'];visibility=np.intersect1d(visibility,candidates)
        row=dict(object_id=oid,image_id=iid,source_type=old['source_type'],camera=c,image_path=str(path),
                 visibility_source=str(hybrid/old['visibility_path']),visible_pixels=pixels,projection=projection,
                 in_affinity_training=iid in trained,observation_role='affinity_train' if iid in trained else 'new_train_split_prompt',
                 direction=old['direction'],eligible=bool(pixels>=cfg['minimum_visible_pixels'] and projection),
                 reason='Full-scene visible M0-candidate contribution; not an object ground-truth mask')
        row['_ids']=visibility;pool.append(row)
    remaining=[r for r in pool if r['eligible']];chosen=[];covered=np.zeros(len(renderer.model.get_xyz),bool)
    for _ in range(cfg['maximum_references']):
        valid=[r for r in remaining if sum((q['source_type']=='real')==(r['source_type']=='real') for q in chosen)<(cfg['real_reference_limit'] if r['source_type']=='real' else cfg['virtual_reference_limit'])]
        if not valid:break
        maximum=max(r['visible_pixels'] for r in valid)
        def score(r):
            ids=r['_ids'];new=float((~covered[ids]).sum()/max(len(candidates),1))
            angle=1. if not chosen else min(np.arccos(np.clip(np.dot(r['direction'],q['direction']),-1,1))/np.pi for q in chosen)
            return (.5*np.sqrt(r['visible_pixels']/maximum)+.35*min(new*3,1)+.15*min(angle*3,1))*(1.12 if r['source_type']=='real' else 1.)
        best=max(valid,key=score);best['selection_score']=float(score(best));best['new_visible_gaussians']=int((~covered[best['_ids']]).sum())
        covered[best['_ids']]=True;chosen.append(best);remaining.remove(best)
    selections[oid]=dict(mode='new_prompts_frozen_feature',views=[{k:v for k,v in r.items() if k!='_ids'} for r in chosen],candidate_views=[{k:v for k,v in r.items() if k!='_ids'} for r in pool])
    for r in chosen:tasks[r['image_id']].append((obj,{k:v for k,v in r.items() if k!='_ids'}))
    print('REFERENCE VIEWS',obj['name_en'],len(chosen),[r['image_id'] for r in chosen],flush=True)
write(out/'view_selection.json',selections)
model=sam_model_registry['vit_h'](checkpoint=str(PROJECT/'models/sam/sam_vit_h_4b8939.pth')).cuda().eval()
model.requires_grad_(False);predictor=SamPredictor(model)
for iid,jobs in tasks.items():
    c=jobs[0][1]['camera'];rgb=np.array(Image.open(jobs[0][1]['image_path']).convert('RGB').resize((c['width'],c['height']),Image.Resampling.BILINEAR));predictor.set_image(rgb)
    for obj,row in jobs:
        folder=out/obj['object_id']/iid;record=folder/'record.json'
        if record.exists():records.append(read(record));continue
        contribution=np.load(folder/'coarse_candidate_contribution.npz')['contribution'].astype(float)
        box=np.array(row['projection']['bbox'],np.float32)
        seeds=spread_points(contribution>.75,3)
        masks,scores,logits=predictor.predict(box=box,multimask_output=True)
        # Separate clicks preserve alternative part hypotheses instead of forcing all pixels into one SAM object.
        for point in seeds[:2]:
            pm,ps,pl=predictor.predict(box=box,point_coords=np.array([point],np.float32),point_labels=np.array([1]),multimask_output=True)
            masks=np.concatenate([masks,pm]);scores=np.concatenate([scores,ps])
        np.savez_compressed(folder/'sam_candidates.npz',masks=masks,scores=scores)
        qualities=[];x0,y0,x1,y1=np.round(box).astype(int);region=np.zeros(rgb.shape[:2],bool);region[y0:y1+1,x0:x1+1]=True
        for j,mask in enumerate(masks):
            intersection=float(contribution[mask].sum());precision=intersection/max(int(mask.sum()),1);recall=intersection/max(float(contribution.sum()),1e-8)
            outside=float((mask&~region).sum()/max(mask.sum(),1));valid=bool(scores[j]>=.72 and outside<=.15 and mask.sum()>=100 and precision>=.50 and recall>=.25)
            qualities.append(dict(index=j,predicted_iou=float(scores[j]),coarse_precision=precision,coarse_recall=recall,outside=outside,valid=valid,score=.7*2*precision*recall/max(precision+recall,1e-8)+.3*float(scores[j])))
        valid=[q for q in qualities if q['valid']];row.update(accepted=False,sam_candidates=qualities,automatic_seed_points=seeds,mask_is_not_ground_truth=True)
        save(folder/'rgb.jpg',rgb);save(folder/'full_scene_render.jpg',renderer.rgb(c))
        if valid:
            best=max(valid,key=lambda q:q['score']);mask=masks[best['index']];points=spread_points(mask&(contribution>.75),cfg['points_per_reference'])
            row.update(accepted=bool(points),selected_index=best['index'],points_xy=points,mask_path=str((folder/'mask.png').relative_to(ROOT)),prompt_source='Automatic 3x3 spatially distributed safe SAM/candidate intersections')
            save(folder/'mask.png',mask.astype(np.uint8)*255);overlay=rgb.copy();overlay[mask]=(overlay[mask]*.5+[128,15,0]).clip(0,255).astype(np.uint8)
            for x,y in points:cv2.circle(overlay,(x,y),5,(30,255,30),2)
            save(folder/'overlay.jpg',overlay)
        else:
            row['reason']='No SAM candidate passes coarse visibility sanity checks';save(folder/'overlay.jpg',rgb)
        write(record,row);records.append(row)
        print('FRESH PROMPT',obj['name_en'],iid,'accepted',row['accepted'],'points',len(row.get('points_xy',[])),flush=True)
write(out/'records.json',records)
for obj in objects:
    rows=[r for r in records if r['object_id']==obj['object_id']]
    if rows:grid([out/obj['object_id']/r['image_id']/'overlay.jpg' for r in rows],out/obj['object_id']/'overview.jpg',labels=[r['image_id']+' '+str(r['accepted']) for r in rows],columns=3,tile=(480,330))
write(out/'summary.json',dict(objects_total=33,objects_reusing_v1=len(reuse),objects_with_new_attempts=len(selections)-len(reuse),references=len(records),accepted=sum(r['accepted'] for r in records),heldout_used=False,training_modified=False))
