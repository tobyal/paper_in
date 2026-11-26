"""Inspect SAGA instances using the complete native scene for occluded projections."""
import argparse,cv2
from common import *
from industrial_world_model.render import Renderer
p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,default=10000);p.add_argument('--tag',default='');args=p.parse_args();folder=ROOT/(f'outputs/A/extractions/iteration_{args.iteration}'+('_'+args.tag if args.tag else ''));summary=read(folder/'summary.json');objects={o['object_id']:o for o in read(ROOT/'inputs/objects.json')};renderer=Renderer(NativeContext());refs=read(ROOT/'outputs/A/reference_prompts/records.json');cameras={c['image_id']:c for c in read(ROOT/'inputs/training_cameras.json')};gallery=[];labels=[];overlay_gallery=[];overlay_labels=[];groups=[]
palette=[[.95,.25,.18],[.15,.7,1],[.95,.7,.12],[.4,.9,.25],[.75,.3,.95],[1,.4,.7],[.1,.85,.75],[.7,.7,1],[.8,.55,.25],[.65,1,.8]]
for index,row in enumerate(summary['objects']):
    if 'gaussian_indices' not in row:continue
    oid=row['object_id'];obj=objects[oid];ids=np.load(ROOT/row['gaussian_indices']);dest=folder/'objects'/oid/'visualizations';dest.mkdir(parents=True,exist_ok=True);groups.append((ids,palette[index%len(palette)]));stats=[]
    for axis in ['oblique','side','top']:
        camera=renderer.virtual(obj['bbox']['center'],obj['bbox']['size'],axis,width=640);image=renderer.rgb(camera,ids);path=dest/(axis+'.jpg');save(path,image);write(dest/(axis+'_camera.json'),camera);gallery.append(path);labels.append(obj['name_en']+' / '+axis)
    candidate=np.load(ROOT/'inputs/geometry/object_candidates'/oid/'gaussian_ids.npy');camera=renderer.virtual(obj['bbox']['center'],obj['bbox']['size'],'oblique',width=640);path=dest/'coarse_candidate_reference.jpg';save(path,renderer.rgb(camera,candidate));gallery.append(path);labels.append('COARSE PRIOR reference / '+str(len(ids))+' selected')
    useful=[r for r in refs if r['object_id']==oid and r['accepted']]
    for ref in useful:
        iid=ref['image_id'];camera=scaled_camera(cameras[iid],width=1200);rgb=np.array(Image.open(ROOT/cameras[iid]['input_path']).convert('RGB').resize((camera['width'],camera['height'])));contribution=renderer.contribution(camera,ids);mask=contribution>.5;overlay=rgb.copy();overlay[mask]=(overlay[mask]*.4+[153,0,0]).clip(0,255).astype(np.uint8)
        save(dest/(iid+'_mask.png'),mask.astype(np.uint8)*255);np.savez_compressed(dest/(iid+'_contribution.npz'),contribution=contribution);save(dest/(iid+'_overlay.jpg'),overlay);save(dest/(iid+'_highlight.jpg'),renderer.highlight(camera,[(ids,[1,.1,.05])]))
        prior=np.array(Image.open(ROOT/ref['mask_path']).resize((camera['width'],camera['height']),Image.Resampling.NEAREST))>0;inter=(mask&prior).sum();union=(mask|prior).sum();stats.append(dict(image_id=iid,mask_pixels=int(mask.sum()),input_prompt_consistency_iou=float(inter/max(union,1)),is_accuracy=False))
        overlay_gallery.append(dest/(iid+'_overlay.jpg'));overlay_labels.append(obj['name_en']+' '+iid[-12:])
    write(dest/'projection_checks.json',stats)
grid(gallery,folder/'independent_objects_overview.jpg',labels=labels,columns=4,tile=(400,340));grid(overlay_gallery,folder/'training_projection_overview.jpg',labels=overlay_labels,columns=3,tile=(500,330));summary['rendered_objects']=len(groups);write(folder/'summary.json',summary)
print('RENDERED INSTANCES',len(groups))
