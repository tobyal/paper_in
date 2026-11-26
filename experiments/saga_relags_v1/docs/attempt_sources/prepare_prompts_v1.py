"""Fresh M0 box-prompted reference masks; optional supervision for official SAGA."""
import collections,shutil
import cv2,torch
from segment_anything import sam_model_registry,SamPredictor
from common import *
from industrial_world_model.hybrid_views.geometry import box_projection

cfg=read(ROOT/'configs/experiment.json');focus=read(ROOT/'inputs/focus_objects.json');T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])
manifest=read(ROOT/'inputs/manifest.json');hybrid=PROJECT/manifest['hybrid_observations'];selected=read(hybrid/'selected_views.json')
images={im['image_id']:im for im in read(ROOT/'inputs/training_cameras.json')};tasks=collections.defaultdict(list)
for obj in focus:
    pool=[r for r in selected[obj['object_id']] if r['image_id'] in images]
    real=sorted([r for r in pool if r['source_type']=='real'],key=lambda r:(r['image_coverage']>.8,r['visible_fraction']),reverse=True)[:2]
    virtual=sorted([r for r in pool if r['source_type']!='real'],key=lambda r:r['visible_fraction'],reverse=True)[:1]
    for row in real+virtual:tasks[row['image_id']].append(obj)
model=sam_model_registry['vit_h'](checkpoint=str(PROJECT/'models/sam/sam_vit_h_4b8939.pth')).cuda().eval();model.requires_grad_(False);predictor=SamPredictor(model);records=[]
for iid,objs in tasks.items():
    im=images[iid];assert im['split']=='train';camera=scaled_camera(im,downsample=cfg['sam_downsample']);rgb=cv2.resize(np.array(Image.open(ROOT/im['input_path']).convert('RGB')),(camera['width'],camera['height']),interpolation=cv2.INTER_LINEAR)
    predictor.set_image(rgb);auto=ROOT/'inputs/saga_dataset/sam_masks'/(iid+'.pt');backup=ROOT/'outputs/A/sam_automatic_original'/(iid+'.pt');backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(auto,backup)
    original=torch.load(backup,map_location='cpu');add=[]
    for obj in objs:
        folder=ROOT/'outputs/A/reference_prompts'/obj['object_id']/iid;folder.mkdir(parents=True,exist_ok=True);projection=box_projection(obj['bbox'],T,camera)
        row=dict(object_id=obj['object_id'],image_id=iid,source_type=im['source_type'],accepted=False,camera=camera,prompt_type='M0 projected box',input_prompt_is_not_ground_truth=True)
        if projection:
            box=np.array(projection['bbox'],np.float32);masks,scores,logits=predictor.predict(box=box,multimask_output=True);np.savez_compressed(folder/'sam_candidates.npz',masks=masks,scores=scores,logits=logits)
            x0,y0,x1,y1=np.round(box).astype(int);region=np.zeros(rgb.shape[:2],bool);region[y0:y1+1,x0:x1+1]=True;qualities=[]
            for j,mask in enumerate(masks):
                outside=float((mask&~region).sum()/max(mask.sum(),1));occupancy=float((mask&region).sum()/max(region.sum(),1));valid=bool(scores[j]>=.75 and outside<=.15 and occupancy>=.05 and mask.sum()>=128)
                qualities.append(dict(index=j,predicted_iou=float(scores[j]),outside_box_fraction=outside,box_occupancy=occupancy,valid=valid));save(folder/f'candidate_{j}.png',mask.astype(np.uint8)*255)
            valid=[q for q in qualities if q['valid']];row.update(projected_box=projection,candidates=qualities)
            if valid:
                best=max(valid,key=lambda q:q['predicted_iou']);mask=masks[best['index']];add.append(torch.from_numpy(mask));row.update(accepted=True,selected_index=best['index'],mask_path=str((folder/'mask.png').relative_to(ROOT)),reason='Fresh SAM box prompt; retained as auxiliary M0 prior, not final 3D labels')
                save(folder/'mask.png',mask.astype(np.uint8)*255);overlay=rgb.copy();overlay[mask]=(overlay[mask]*.45+np.array([255,60,40])*.55).astype(np.uint8);save(folder/'overlay.jpg',overlay)
            else:row['reason']='All SAM prompt candidates failed quality checks'
        else:row['reason']='No usable projected M0 box'
        write(folder/'record.json',row);records.append(row)
    torch.save(torch.cat([original,torch.stack(add)]) if add else original,auto)
    print('REFERENCE MASKS',iid,'accepted',len(add),'/',len(objs),flush=True)
write(ROOT/'outputs/A/reference_prompts/records.json',records)
paths=[ROOT/Path(r['mask_path']).parent/'overlay.jpg' for r in records if r['accepted']];grid(paths,ROOT/'outputs/A/reference_prompts/overview.jpg',labels=[r['object_id']+' '+r['image_id'][-12:] for r in records if r['accepted']])
write(ROOT/'outputs/A/reference_prompts/summary.json',dict(total=len(records),accepted=sum(r['accepted'] for r in records),official_automatic_masks_preserved=True,heldout_used=False,old_semantic_masks_used=False))
