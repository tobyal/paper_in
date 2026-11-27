"""SAM-only reference generation from RGB; review edits never read benchmark predictions."""
from common import *
import argparse,collections,torch
from segment_anything import sam_model_registry,SamPredictor
p=argparse.ArgumentParser();p.add_argument('--revision',default='initial');p.add_argument('--edits',default='prompt_edits.json');a=p.parse_args();base=ROOT/'evaluation/pseudo_ground_truth';tasks=read(base/'tasks.json');edits=read(base/a.edits) if (base/a.edits).exists() else {}
selected=[t for t in tasks if t['projection'] and (a.revision=='initial' or t['task_id'] in edits)]
model=sam_model_registry['vit_h'](checkpoint=str(PROJECT/'models/sam/sam_vit_h_4b8939.pth')).cuda().eval();model.requires_grad_(False);predictor=SamPredictor(model);bycamera=collections.defaultdict(list)
for t in selected:bycamera[t['camera_id']].append(t)
for iid,items in bycamera.items():
    rgb=np.array(Image.open(base/'rgb'/(iid+'.png')).convert('RGB'));predictor.set_image(rgb)
    for task in items:
        dest=base/'objects'/task['task_id']/a.revision
        if (dest/'record.json').exists():continue
        edit=edits.get(task['task_id'],{}) if a.revision!='initial' else {};box=edit.get('box',task['projection']['bbox']);points=edit.get('points',[]);labels=edit.get('labels',[])
        masks,scores,logits=predictor.predict(box=np.array(box,np.float32),point_coords=np.array(points,np.float32) if points else None,point_labels=np.array(labels,np.int32) if points else None,multimask_output=True)
        choice=int(edit.get('candidate',np.argmax(scores)));dest.mkdir(parents=True,exist_ok=True);np.savez_compressed(dest/'sam_candidates.npz',masks=masks,scores=scores,logits=logits)
        mask=masks[choice];save(dest/'mask.png',mask.astype('uint8')*255);overlay=rgb.copy();overlay[mask]=(overlay[mask]*.5+np.array([20,235,90])*.5).astype('uint8');save(dest/'overlay.jpg',overlay)
        record=dict(task);record.update(revision=a.revision,box=box,points=points,point_labels=labels,scores=scores.tolist(),selected_candidate=choice,mask_pixels=int(mask.sum()),source='SAM-assisted Pseudo-GT; fresh original RGB; no retrieval predictions',notes=edit.get('note','Initial projected box, highest SAM predicted IoU; requires visual review'));write(dest/'record.json',record)
    print('SAM',a.revision,iid,len(items),flush=True)
