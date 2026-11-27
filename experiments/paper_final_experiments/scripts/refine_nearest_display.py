"""Select complete illustrative views; nearest queries and IDs stay unchanged."""
from common import *
from industrial_world_model.hybrid_views.geometry import box_projection
import torch,shutil
from m0.native_3dgs import subset_model
root=ROOT/'E05_multiview_application/nearest';rows=read(root/'summary.json');backup=root/'display_selection_previous.json'
if not backup.exists():write(backup,rows)
r=renderer();wm=world_model();T=np.array(Context.state['scene']['transform']);views=read(BENCH/'configs/evaluation_views.json')['cameras']
for row in rows:
    d=root/row['case_id'];raw=read(d/'query.json');ids=np.load(d/'gaussian_ids.npy');assert np.array_equal(ids,wm.gaussian_ids(raw));visible_ids=ids if len(ids) else union([candidates(o) for o in raw['matched_object_ids']]);stats=[]
    for iid,c in views.items():
        projections=[box_projection(wm.byid[o]['bbox'],T,c) for o in raw['matched_object_ids']];coverage=min(p['image_coverage'] if p else 0 for p in projections);anchor=box_projection(wm.byid[row['anchor_id']]['bbox'],T,c);ac=anchor['image_coverage'] if anchor else 0;pixels=int((r.contribution(c,visible_ids)>.5).sum());stats.append(dict(camera_id=iid,target_box_coverage=coverage,anchor_box_coverage=ac,visible_pixels=pixels,complete=coverage>.98 and ac>.9 and pixels>100))
    eligible=[v for v in stats if v['complete']];best=max(eligible or stats,key=lambda s:s['visible_pixels']*s['target_box_coverage']**3);iid=best['camera_id'];c=scaled(views[iid],1500)
    save(d/'original.png',rgb(c));save(d/'scene.png',r.rgb(c));save(d/'highlight.png',r.highlight(c,[(ids,[.95,.25,.12]),(candidates(row['anchor_id']),[.1,.65,.85])]));write(d/'camera.json',c)
    if len(ids):
        model=subset_model(r.model,ids)
        with torch.inference_mode():alpha=r.pass_colors(c,torch.ones((len(ids),3),device='cuda'),model=model).permute(1,2,0).cpu().numpy()
        isolated=(r.rgb(c,ids).astype(float)+255*(1-alpha)).clip(0,255).astype(np.uint8)
    else:isolated=np.full((c['height'],c['width'],3),255,np.uint8)
    save(d/'isolated.png',isolated);write(d/'display_candidate_views.json',stats);row['chosen_camera']=iid;row['view_selection']='Prefer target OBB coverage >0.98 and anchor >0.9, then visible pixels; illustrative view only, no evaluation camera change';row['selected_display_quality']=best;print(row['case_id'],iid,best,flush=True)
write(root/'summary.json',rows)
