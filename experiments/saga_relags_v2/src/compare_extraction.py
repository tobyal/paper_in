"""Bounded fixed-prompt threshold/gate comparisons, not ground-truth scoring."""
from common import *
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection
import cv2
objects={o['object_id']:o for o in read(ROOT/'inputs/objects.json')};cfg=read(ROOT/'configs/refinement.json')
renderer=Renderer(NativeContext());base=ROOT/'outputs/A/extractions/refined';out=ROOT/'outputs/A/bounded_comparison';rows=[]
for oid in cfg['threshold_comparison']['objects']:
    obj=objects[oid];cand=candidate_ids(oid);scores=np.load(base/'objects'/oid/'affinity_scores.npy');paths=[];labels=[]
    for threshold in cfg['threshold_comparison']['thresholds']:
        ids=cand[scores[cand]>threshold];dest=out/oid/f'threshold_{threshold:.2f}';dest.mkdir(parents=True,exist_ok=True);np.save(dest/'gaussian_indices.npy',ids)
        for axis in ['oblique','side','top']:
            camera=renderer.virtual(obj['bbox']['center'],obj['bbox']['size'],axis,width=640);path=dest/(axis+'.jpg');save(path,renderer.rgb(camera,ids));paths.append(path);labels.append(f'{obj["name_en"]} t={threshold} {axis}')
        camera=read(base/'objects'/oid/'visualizations/training_camera.json');rgb=np.array(Image.open(PROJECT/'data/images'/camera['filename']).convert('RGB').resize((camera['width'],camera['height'])))
        contribution=renderer.contribution(camera,ids);mask=contribution>.5;overlay=rgb.copy();overlay[mask]=(overlay[mask]*.45+[140,10,0]).clip(0,255).astype(np.uint8)
        projection=box_projection(obj['bbox'],np.array(renderer.ctx.state['scene']['transform']),camera);x0,y0,x1,y1=np.array(projection['bbox']).astype(int);path=dest/'projection.jpg';save(path,overlay[y0:y1+1,x0:x1+1]);paths.append(path);labels.append(f't={threshold} training projection')
        rows.append(dict(object_id=oid,threshold=threshold,gaussians=len(ids),fixed_prompts=True,fixed_scale=True,heldout_used=False))
    grid(paths,out/oid/'thresholds.jpg',labels,columns=4,tile=(420,340))
oid=cfg['scale_comparison']['objects'][0];obj=objects[oid];paths=[];labels=[]
for tag in ['scale_lower','refined','scale_upper']:
    d=ROOT/'outputs/A/extractions'/tag/'objects'/oid;ids=np.load(d/'gaussian_indices.npy');prompt=read(d/'prompt.json')
    for axis in ['oblique','side','top']:
        camera=renderer.virtual(obj['bbox']['center'],obj['bbox']['size'],axis,width=640);path=out/oid/tag/(axis+'.jpg');save(path,renderer.rgb(camera,ids));paths.append(path);labels.append(f'gate={prompt["normalized_scale"]:.3f} {axis}')
grid(paths,out/oid/'scales.jpg',labels,columns=3,tile=(480,350));write(out/'statistics.json',rows)
